"""
signals.py
==========
Generates trading signals from candle data using RSI and MACD.
Uses manual calculations — no pandas-ta dependency needed.
"""

import asyncio
from typing import Optional
import pandas as pd
import numpy as np

from utils.logger import log, log_error

# OTC pairs to scan in order of preference
OTC_PAIRS = [
    "EURUSD_otc",
    "AUDUSD_otc",
    "USDCAD_otc",
    "USDCHF_otc",
    "USDJPY_otc",
    "EURJPY_otc",
    "EURGBP_otc",
    "CADJPY_otc",
    "AUDCAD_otc",
    "NZDUSD_otc",
    "AUDNZD_otc",
    "CHFJPY_otc",
]

PAIR_DISPLAY = {
    "EURUSD_otc":  "EUR/USD OTC",
    "AUDUSD_otc":  "AUD/USD OTC",
    "USDCAD_otc":  "USD/CAD OTC",
    "USDCHF_otc":  "USD/CHF OTC",
    "USDJPY_otc":  "USD/JPY OTC",
    "EURJPY_otc":  "EUR/JPY OTC",
    "EURGBP_otc":  "EUR/GBP OTC",
    "CADJPY_otc":  "CAD/JPY OTC",
    "AUDCAD_otc":  "AUD/CAD OTC",
    "NZDUSD_otc":  "NZD/USD OTC",
    "AUDNZD_otc":  "AUD/NZD OTC",
    "CHFJPY_otc":  "CHF/JPY OTC",
    "AEDCNY_otc":  "AED/CNY OTC",
}

FALLBACK_PAIR      = "EURUSD_otc"
FALLBACK_DIRECTION = "put"
FALLBACK_PAYOUT    = 85
MIN_PAYOUT         = 75


def _compute_signal(candles: list) -> Optional[str]:
    """
    Returns 'put' or 'call' based on RSI + MACD.
    Pure pandas/numpy — no external TA library needed.
    """
    if len(candles) < 30:
        return None

    try:
        df = pd.DataFrame(candles)
        df = df.sort_values("time").reset_index(drop=True)
        close = df["close"].astype(float)

        # ── RSI(14) manual ────────────────────────────────────────────────
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - 100 / (1 + rs)

        # ── MACD(12,26,9) manual ──────────────────────────────────────────
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        last_rsi  = float(rsi.iloc[-1] or 50)
        last_hist = float(histogram.iloc[-1] or 0)
        prev_hist = float(histogram.iloc[-2] or 0)

        buy_signals  = 0
        sell_signals = 0

        # RSI conditions
        if last_rsi < 30:
            buy_signals += 2
        elif last_rsi < 45:
            buy_signals += 1
        elif last_rsi > 70:
            sell_signals += 2
        elif last_rsi > 55:
            sell_signals += 1

        # MACD histogram cross
        if prev_hist < 0 and last_hist > 0:
            buy_signals += 2
        elif last_hist > 0:
            buy_signals += 1
        elif prev_hist > 0 and last_hist < 0:
            sell_signals += 2
        elif last_hist < 0:
            sell_signals += 1

        # Last 3 candles direction
        last3 = close.tail(3).values
        if len(last3) == 3:
            if last3[2] < last3[1] < last3[0]:
                sell_signals += 1
            elif last3[2] > last3[1] > last3[0]:
                buy_signals += 1

        if sell_signals > buy_signals:
            return "put"
        elif buy_signals > sell_signals:
            return "call"
        return None

    except Exception as e:
        log_error(f"_compute_signal error: {e}", exc_info=True)
        return None


async def generate_signal(api) -> dict:
    """
    Scans OTC_PAIRS, picks the one with the best payout + valid signal.
    Returns a dict: {pair, direction, payout, display_name}
    Falls back to EURUSD_otc if nothing found.
    """
    best = None
    best_payout = 0

    assets = {}
    try:
        assets = api.get_assets() or {}
    except Exception as e:
        log_error(f"get_assets error: {e}")

    for pair in OTC_PAIRS:
        try:
            # Get payout
            payout = 0
            if pair in assets:
                payout = assets[pair].get("payout", 0) or 0
            else:
                try:
                    payout = api.get_payout(pair) or 0
                except Exception:
                    pass

            if payout < MIN_PAYOUT:
                log(f"Skip {pair}: payout {payout}% < {MIN_PAYOUT}%")
                continue

            # Subscribe and get candles
            try:
                api.subscribe(pair, 60)
                await asyncio.sleep(1)
            except Exception:
                pass

            candles = None
            try:
                candles = api.get_historical_candles(pair, period=60, offset=9000, count_request=1)
            except Exception as e:
                log(f"get_historical_candles {pair}: {e}")

            if not candles or len(candles) < 20:
                continue

            direction = _compute_signal(candles)
            if direction is None:
                log(f"{pair}: no clear signal")
                continue

            if payout > best_payout:
                best_payout = payout
                best = {
                    "pair": pair,
                    "direction": direction,
                    "payout": payout,
                    "display_name": PAIR_DISPLAY.get(pair, pair),
                }

        except Exception as e:
            log_error(f"Signal scan {pair}: {e}")
            continue

    if best:
        return best

    # Fallback
    log("Using fallback signal: EURUSD_otc SELL")
    return {
        "pair": FALLBACK_PAIR,
        "direction": FALLBACK_DIRECTION,
        "payout": FALLBACK_PAYOUT,
        "display_name": PAIR_DISPLAY.get(FALLBACK_PAIR, FALLBACK_PAIR),
    }
