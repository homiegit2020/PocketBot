"""
trading_engine.py
=================
Core trading logic:
  - WebSocket connection management per user (SSID-based)
  - Signal generation
  - Martingale trade execution
  - Real-time result reporting via Telegram message edits
"""

import asyncio
import threading
import time
from typing import Optional, Callable

from utils.logger import log, log_error

# Martingale amounts: base $1, multiplier 2.3x
MARTINGALE_BASE       = 1.00
MARTINGALE_MULTIPLIER = 2.3
MARTINGALE_STEPS      = [
    1.00,    # Step 1
    2.30,    # Step 2
    5.29,    # Step 3
    12.17,   # Step 4
    27.99,   # Step 5
]


def _get_martingale_amount(base: float, step: int) -> float:
    """Calculate Martingale amount for a given step (1-indexed)."""
    if step <= 1:
        return base
    amount = base
    for _ in range(step - 1):
        amount *= MARTINGALE_MULTIPLIER
    return round(amount, 2)


class PocketConnection:
    """
    Manages a single user's Pocket Option WebSocket connection.
    Wraps the chema-creator PocketOptionApi stable_api.PocketOption.
    """

    def __init__(self, ssid: str):
        self.ssid = ssid
        self._api = None
        self._connected = False
        self._lock = asyncio.Lock()

    def _load_api(self):
        try:
            from pocketoptionapi.stable_api import PocketOption
            return PocketOption(self.ssid)
        except ImportError:
            log_error("pocketoptionapi not installed — run: pip install git+https://github.com/chema-creator/PocketOptionApi.git")
            return None

    async def connect(self, timeout: float = 35.0) -> bool:
        async with self._lock:
            if self._connected and self._api:
                return True
            try:
                api = await asyncio.get_event_loop().run_in_executor(None, self._load_api)
                if api is None:
                    return False

                ok, err = await asyncio.get_event_loop().run_in_executor(None, api.connect)
                if not ok:
                    log_error(f"PocketOption connect failed: {err}")
                    return False

                # Wait for time sync
                deadline = time.time() + timeout
                while time.time() < deadline:
                    connected = await asyncio.get_event_loop().run_in_executor(None, api.check_connect)
                    synced = await asyncio.get_event_loop().run_in_executor(None, api.is_time_synced)
                    if connected and synced:
                        break
                    await asyncio.sleep(0.2)

                connected = await asyncio.get_event_loop().run_in_executor(None, api.check_connect)
                if not connected:
                    log_error("PocketOption: connection timeout")
                    return False

                self._api = api
                self._connected = True
                log("✅ Pocket Option WebSocket connected")
                return True

            except Exception as e:
                log_error(f"PocketConnection.connect error: {e}", exc_info=True)
                return False

    async def disconnect(self):
        try:
            if self._api:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._api.disconnect_websocket
                )
        except Exception:
            pass
        self._connected = False
        self._api = None

    def is_connected(self) -> bool:
        if not self._connected or self._api is None:
            return False
        try:
            return self._api.check_connect()
        except Exception:
            return False

    async def get_balance(self) -> Optional[float]:
        try:
            return await asyncio.get_event_loop().run_in_executor(None, self._api.get_balance)
        except Exception:
            return None

    async def get_assets(self) -> dict:
        try:
            return await asyncio.get_event_loop().run_in_executor(None, self._api.get_assets) or {}
        except Exception:
            return {}

    async def get_payout(self, pair: str) -> int:
        try:
            p = await asyncio.get_event_loop().run_in_executor(None, self._api.get_payout, pair)
            return int(p or 0)
        except Exception:
            return 0

    async def subscribe(self, pair: str, period: int = 60) -> bool:
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._api.subscribe, pair, period
            )
        except Exception:
            return False

    async def get_historical_candles(self, pair: str, period: int = 60, offset: int = 9000) -> Optional[list]:
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._api.get_historical_candles, pair, period, None, offset, 1
            )
        except Exception as e:
            log_error(f"get_historical_candles {pair}: {e}")
            return None

    async def buy(self, amount: float, pair: str, direction: str, duration: int) -> tuple:
        """Returns (order_dict, success_bool)"""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._api.buy, amount, pair, direction, duration
            )
        except Exception as e:
            log_error(f"buy error: {e}", exc_info=True)
            return {}, False

    async def check_win(self, order_id: str, timeout: float = 120.0) -> Optional[dict]:
        """Polls for trade result. Returns deal dict or None on timeout."""
        loop = asyncio.get_event_loop()
        result_holder = []
        event = asyncio.Event()

        def _cb(deal):
            result_holder.append(deal)
            loop.call_soon_threadsafe(event.set)

        def _do_check():
            self._api.check_win(order_id, callback=_cb)

        await loop.run_in_executor(None, _do_check)

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return result_holder[0] if result_holder else None
        except asyncio.TimeoutError:
            return None

    @property
    def api(self):
        return self._api


# ── Per-user connection pool ──────────────────────────────────────────────────

_connections: dict[int, PocketConnection] = {}
_conn_lock = asyncio.Lock()


async def get_connection(telegram_id: int, ssid: str) -> Optional[PocketConnection]:
    """Get or create a connection for a user. Auto-reconnects if dead."""
    async with _conn_lock:
        conn = _connections.get(telegram_id)
        if conn and conn.is_connected():
            return conn
        # Create new
        conn = PocketConnection(ssid)
        ok = await conn.connect()
        if ok:
            _connections[telegram_id] = conn
            return conn
        return None


async def close_connection(telegram_id: int):
    async with _conn_lock:
        conn = _connections.pop(telegram_id, None)
        if conn:
            await conn.disconnect()


# ── Trade execution ───────────────────────────────────────────────────────────

async def execute_trade_with_martingale(
    telegram_id: int,
    ssid: str,
    pair: str,
    direction: str,
    trade_time: int,
    base_amount: float,
    max_steps: int,
    mode: str,
    on_step_update: Optional[Callable] = None,
) -> dict:
    """
    Executes one trade with full Martingale recovery.
    Calls on_step_update(steps_list) after each step result.
    Returns summary dict.
    """
    conn = await get_connection(telegram_id, ssid)
    if conn is None:
        return {"success": False, "error": "WebSocket connection failed"}

    steps = []
    net_profit = 0.0
    final_balance = None

    for step_num in range(1, max_steps + 1):
        amount = _get_martingale_amount(base_amount, step_num)

        # Announce step is in progress
        steps.append({"step": step_num, "amount": amount, "win": None})
        if on_step_update:
            try:
                await on_step_update(steps.copy())
            except Exception:
                pass

        # Place trade
        order_data, order_ok = await conn.buy(amount, pair, direction, trade_time)

        if not order_ok or not order_data:
            log_error(f"Trade step {step_num} failed to open for user {telegram_id}")
            steps[-1]["win"] = False
            steps[-1]["profit"] = 0.0
            if on_step_update:
                try:
                    await on_step_update(steps.copy())
                except Exception:
                    pass
            continue

        order_id = order_data.get("id", "")
        log(f"Order opened: {order_id}, step {step_num}, amount {amount}")

        # Wait for result (trade_time + buffer)
        wait_time = float(trade_time) + 5.0
        deal = await conn.check_win(order_id, timeout=wait_time + 60)

        if deal is None:
            log(f"Trade {order_id} timed out waiting for result")
            steps[-1]["win"] = False
            steps[-1]["profit"] = 0.0
        else:
            profit = float(deal.get("profit", 0.0) or 0.0)
            win = profit > amount * 0.5  # profit > half amount = win
            steps[-1]["win"] = win
            steps[-1]["profit"] = profit

            if win:
                net_profit += profit - amount  # net gain
                log(f"Step {step_num} WIN: profit={profit}")
                final_balance = await conn.get_balance()
                if on_step_update:
                    try:
                        await on_step_update(steps.copy())
                    except Exception:
                        pass
                break
            else:
                net_profit -= amount  # lose the stake
                log(f"Step {step_num} LOSS: amount={amount}")

        if on_step_update:
            try:
                await on_step_update(steps.copy())
            except Exception:
                pass

        # Small pause between martingale steps
        await asyncio.sleep(1.5)

    if final_balance is None:
        final_balance = await conn.get_balance()

    overall_win = any(s.get("win") for s in steps)

    return {
        "success": True,
        "steps": steps,
        "net_profit": round(net_profit, 2),
        "win": overall_win,
        "balance": final_balance,
    }
