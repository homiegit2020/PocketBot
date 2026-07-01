"""
session_manager.py
==================
Auto-refreshes all user sessions every 6 hours.
Handles re-login if a session expires during trading.
"""

import asyncio
from datetime import datetime

from database import db
from services.pocket_auth import refresh_session
from utils.logger import log, log_error


async def refresh_all_sessions() -> None:
    """Scheduled job: re-login all users with stored credentials."""
    log("🔄 Auto-refreshing all sessions...")
    users = await db.get_all_users()
    refreshed = 0
    failed = 0

    for user in users:
        if not user.get("email") or not user.get("password"):
            continue
        try:
            result = await refresh_session(user["email"], user["password"])
            if result.get("success"):
                await db.update_user_session(
                    user["telegram_id"],
                    ssid=result["ssid"],
                    po_session=result["po_session"],
                    po_uid=result["po_uid"],
                )
                refreshed += 1
            else:
                failed += 1
                log(f"Session refresh failed for {user['telegram_id']}: {result.get('error')}")
        except Exception as e:
            failed += 1
            log_error(f"Session refresh exception for {user['telegram_id']}: {e}")

        # Throttle — don't hammer the server
        await asyncio.sleep(3)

    log(f"✅ Session refresh done: {refreshed} ok, {failed} failed")


async def ensure_fresh_session(telegram_id: int) -> bool:
    """
    Called before trading. Re-logins if session is missing or expired.
    Returns True if session is now valid.
    """
    user = await db.get_user(telegram_id)
    if not user:
        return False

    if user.get("ssid"):
        return True  # Assume valid until proven otherwise

    # No session — try to refresh
    if user.get("email") and user.get("password"):
        result = await refresh_session(user["email"], user["password"])
        if result.get("success"):
            await db.update_user_session(
                telegram_id,
                ssid=result["ssid"],
                po_session=result["po_session"],
                po_uid=result["po_uid"],
            )
            return True

    return False
