import os
from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, update, func, desc

from database.models import Base, User, Trade, ActivityLog, BotSettings
from utils.logger import log, log_error

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log("✅ Database initialized")


# ── User CRUD ─────────────────────────────────────────────────────────────────

async def get_user(telegram_id: int) -> Optional[dict]:
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(User).where(User.telegram_id == telegram_id))
        u = result.scalar_one_or_none()
        return _user_to_dict(u) if u else None


async def create_user(telegram_id: int) -> dict:
    async with AsyncSessionLocal() as s:
        u = User(telegram_id=telegram_id, created_at=datetime.utcnow(), last_active=datetime.utcnow())
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return _user_to_dict(u)


async def get_or_create_user(telegram_id: int) -> dict:
    u = await get_user(telegram_id)
    if not u:
        u = await create_user(telegram_id)
    return u


async def update_user(telegram_id: int, **kwargs) -> None:
    kwargs["last_active"] = datetime.utcnow()
    async with AsyncSessionLocal() as s:
        await s.execute(update(User).where(User.telegram_id == telegram_id).values(**kwargs))
        await s.commit()


async def update_user_session(telegram_id: int, ssid: str, po_session: str, po_uid: str) -> None:
    await update_user(telegram_id, ssid=ssid, po_session=po_session, po_uid=po_uid)


async def get_all_users() -> List[dict]:
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(User).order_by(desc(User.last_active)))
        return [_user_to_dict(u) for u in result.scalars().all()]


async def get_users_page(page: int, per_page: int = 10) -> List[dict]:
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(User).order_by(desc(User.last_active))
            .offset(page * per_page).limit(per_page)
        )
        return [_user_to_dict(u) for u in result.scalars().all()]


async def count_users() -> int:
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(func.count()).select_from(User))
        return result.scalar() or 0


async def count_banned_users() -> int:
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(func.count()).select_from(User).where(User.is_banned == True))
        return result.scalar() or 0


async def count_active_today() -> int:
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=24)
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(func.count()).select_from(User).where(User.last_active >= cutoff)
        )
        return result.scalar() or 0


async def ban_user(telegram_id: int, reason: str = "") -> None:
    await update_user(telegram_id, is_banned=True, ban_reason=reason)
    await log_activity(telegram_id, "ban", f"Banned: {reason}")


async def unban_user(telegram_id: int) -> None:
    await update_user(telegram_id, is_banned=False, ban_reason=None)
    await log_activity(telegram_id, "unban", "Unbanned by admin")


async def search_user_by_email(email: str) -> Optional[dict]:
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(User).where(User.email == email))
        u = result.scalar_one_or_none()
        return _user_to_dict(u) if u else None


# ── Trades ────────────────────────────────────────────────────────────────────

async def save_trade(telegram_id: int, session_number: int, trade_number: int,
                     pair: str, direction: str, steps_taken: int, amount: float,
                     profit: float, balance_after: float, win: bool) -> None:
    async with AsyncSessionLocal() as s:
        t = Trade(
            telegram_id=telegram_id, session_number=session_number,
            trade_number=trade_number, pair=pair, direction=direction,
            steps_taken=steps_taken, amount=amount, profit=profit,
            balance_after=balance_after, win=win, timestamp=datetime.utcnow()
        )
        s.add(t)
        await s.commit()


async def get_user_trades(telegram_id: int) -> List[dict]:
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(Trade).where(Trade.telegram_id == telegram_id)
            .order_by(desc(Trade.timestamp))
        )
        return [_trade_to_dict(t) for t in result.scalars().all()]


async def count_total_trades() -> int:
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(func.count()).select_from(Trade))
        return result.scalar() or 0


# ── Activity log ──────────────────────────────────────────────────────────────

async def log_activity(telegram_id: Optional[int], event_type: str, details: str = "") -> None:
    try:
        async with AsyncSessionLocal() as s:
            entry = ActivityLog(telegram_id=telegram_id, event_type=event_type,
                                details=details, timestamp=datetime.utcnow())
            s.add(entry)
            await s.commit()
    except Exception as e:
        log_error(f"log_activity error: {e}")


async def get_activity_log(limit: int = 50) -> List[dict]:
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(ActivityLog).order_by(desc(ActivityLog.timestamp)).limit(limit)
        )
        return [{"id": a.id, "telegram_id": a.telegram_id, "event_type": a.event_type,
                 "details": a.details, "timestamp": str(a.timestamp)}
                for a in result.scalars().all()]


# ── Bot settings ──────────────────────────────────────────────────────────────

async def get_setting(key: str, default: str = "") -> str:
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(BotSettings).where(BotSettings.key == key))
        row = result.scalar_one_or_none()
        return row.value if row else default


async def set_setting(key: str, value: str) -> None:
    async with AsyncSessionLocal() as s:
        result = await s.execute(select(BotSettings).where(BotSettings.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            s.add(BotSettings(key=key, value=value))
        await s.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_to_dict(u: User) -> dict:
    return {
        "telegram_id":       u.telegram_id,
        "email":             u.email,
        "password":          u.password,
        "account_id":        u.account_id,
        "po_session":        u.po_session,
        "po_uid":            u.po_uid,
        "ssid":              u.ssid,
        "demo_balance":      u.demo_balance or 50000.0,
        "real_balance":      u.real_balance or 0.0,
        "mode":              u.mode or "demo",
        "trade_amount":      u.trade_amount or 1.0,
        "trade_time":        u.trade_time or 60,
        "martingale_steps":  u.martingale_steps or 5,
        "trades_per_session": u.trades_per_session or 10,
        "sessions_completed": u.sessions_completed or 0,
        "is_banned":         u.is_banned or False,
        "ban_reason":        u.ban_reason,
        "created_at":        str(u.created_at),
        "last_active":       str(u.last_active),
    }


def _trade_to_dict(t: Trade) -> dict:
    return {
        "id": t.id, "telegram_id": t.telegram_id,
        "session_number": t.session_number, "trade_number": t.trade_number,
        "pair": t.pair, "direction": t.direction, "steps_taken": t.steps_taken,
        "amount": t.amount, "profit": t.profit, "balance_after": t.balance_after,
        "win": t.win, "timestamp": str(t.timestamp),
    }
