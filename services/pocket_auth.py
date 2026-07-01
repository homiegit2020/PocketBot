"""
pocket_auth.py
==============
Handles Pocket Option account creation and login.
ALL methods are automatic — no manual steps required from the user.

Method order:
  1. Direct HTTP API (fast, may fail on captcha)
  2. Playwright stealth browser (robust, slower)
  3. WebSocket auth attempt (last resort)

Session extraction uses the proven technique from Mastaaa1987/PocketOptionAPI-v2:
  - Login via browser → get cookies → call cabinet page → extract demoSessionId from HTML
"""

import asyncio
import json
import re
import secrets
import string
import traceback
import urllib.parse
from typing import Optional

import aiohttp

from utils.logger import log, log_error

# ── Password generator ────────────────────────────────────────────────────────

def _gen_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        # Ensure at least one digit, one letter, one special char
        if (any(c.isdigit() for c in pwd)
                and any(c.isalpha() for c in pwd)
                and any(c in "!@#$" for c in pwd)):
            return pwd


# ── HTML session extraction ───────────────────────────────────────────────────

def _extract_session_from_html(html: str) -> tuple[Optional[str], Optional[str]]:
    """
    Returns (demo_session_id, uid) from cabinet page HTML.
    Pocket Option embeds these in a JS config object on the page.
    """
    session = None
    uid = None

    # Try various patterns for demoSessionId
    for pat in [
        r'demoSessionId["\s:=]+["\']([a-z0-9A-Z_\-]+)["\']',
        r'"session"\s*:\s*"([a-z0-9A-Z_\-]+)"',
        r"demoSessionId\s*=\s*['\"]([a-z0-9A-Z_\-]+)['\"]",
    ]:
        m = re.search(pat, html)
        if m:
            session = m.group(1)
            break

    # Try various patterns for uid
    for pat in [
        r'"uid"\s*:\s*(\d+)',
        r"uid\s*=\s*(\d+)",
        r"userId\s*[=:]\s*['\"]?(\d+)",
    ]:
        m = re.search(pat, html)
        if m:
            uid = m.group(1)
            break

    return session, uid


def _build_ssid(session: str, uid: str, is_demo: bool = True) -> str:
    if is_demo:
        return (
            f'42["auth",{{"session":"{session}",'
            f'"isDemo":1,"uid":{uid},'
            f'"platform":2,"isFastHistory":true,"isOptimized":true}}]'
        )
    # Real account — session may contain quotes, use json.dumps to escape
    session_escaped = json.dumps(session)[1:-1]  # strip surrounding quotes
    return (
        f'42["auth",{{"session":"{session_escaped}",'
        f'"isDemo":0,"uid":{uid},'
        f'"platform":2,"isFastHistory":true,"isOptimized":true}}]'
    )


# ── Method 1 — Direct HTTP API ────────────────────────────────────────────────

async def _register_via_api(email: str, password: str) -> dict:
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        headers_base = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as sess:
            # Step 1: get CSRF token
            async with sess.get("https://pocketoption.com/en/registration/", headers=headers_base) as resp:
                html = await resp.text()
                site_cookies = {c.key: c.value for c in resp.cookies.values()}
                csrf_m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
                csrf = csrf_m.group(1) if csrf_m else ""

            # Step 2: POST registration
            reg_headers = {
                **headers_base,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-CSRF-TOKEN": csrf,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://pocketoption.com",
                "Referer": "https://pocketoption.com/en/registration/",
            }
            payload = {
                "email": email, "password": password,
                "password_confirmation": password,
                "locale": "en", "currency": "USD", "agree": 1,
            }
            async with sess.post(
                "https://pocketoption.com/api/v1/auth/register",
                json=payload, headers=reg_headers, cookies=site_cookies,
                allow_redirects=True,
            ) as resp:
                data = {}
                try:
                    data = await resp.json()
                except Exception:
                    pass

                resp_cookies = {c.key: c.value for c in resp.cookies.values()}
                all_cookies = {**site_cookies, **resp_cookies}

                if resp.status not in [200, 201]:
                    return {"success": False, "error": f"HTTP {resp.status}: {data}"}

                # Try to get cabinet page to extract session
                cabinet_url = "https://pocketoption.com/en/cabinet/demo-quick-high-low/"
                async with sess.get(cabinet_url, cookies=all_cookies, headers=headers_base) as cab:
                    cab_html = await cab.text()
                    session, uid = _extract_session_from_html(cab_html)

                    if not session or not uid:
                        # Try ci_session cookie
                        ci = all_cookies.get("ci_session", "")
                        if ci:
                            session = urllib.parse.unquote(ci)
                            uid = all_cookies.get("uid", data.get("user", {}).get("id", ""))

                    if session and uid:
                        ssid = _build_ssid(session, str(uid), is_demo=True)
                        return {
                            "success": True,
                            "ssid": ssid, "po_session": session,
                            "po_uid": str(uid), "account_id": str(uid),
                            "demo_balance": 50000.0, "real_balance": 0.0,
                        }

        return {"success": False, "error": "Session not found after HTTP registration"}
    except Exception as e:
        log_error(f"_register_via_api error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def _login_via_api(email: str, password: str) -> dict:
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        headers_base = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as sess:
            async with sess.get("https://pocketoption.com/en/login/", headers=headers_base) as resp:
                html = await resp.text()
                site_cookies = {c.key: c.value for c in resp.cookies.values()}
                csrf_m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
                csrf = csrf_m.group(1) if csrf_m else ""

            login_headers = {
                **headers_base,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-CSRF-TOKEN": csrf,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://pocketoption.com",
                "Referer": "https://pocketoption.com/en/login/",
            }
            async with sess.post(
                "https://pocketoption.com/api/v1/auth/login",
                json={"email": email, "password": password, "locale": "en"},
                headers=login_headers, cookies=site_cookies, allow_redirects=True,
            ) as resp:
                data = {}
                try:
                    data = await resp.json()
                except Exception:
                    pass

                resp_cookies = {c.key: c.value for c in resp.cookies.values()}
                all_cookies = {**site_cookies, **resp_cookies}

                if resp.status != 200:
                    return {"success": False, "error": f"HTTP {resp.status}"}

                cabinet_url = "https://pocketoption.com/en/cabinet/demo-quick-high-low/"
                async with sess.get(cabinet_url, cookies=all_cookies, headers=headers_base) as cab:
                    cab_html = await cab.text()
                    session, uid = _extract_session_from_html(cab_html)

                    if not session or not uid:
                        ci = all_cookies.get("ci_session", "")
                        if ci:
                            session = urllib.parse.unquote(ci)
                            uid = all_cookies.get("uid", str(data.get("user", {}).get("id", "")))

                    if session and uid:
                        ssid = _build_ssid(session, str(uid), is_demo=True)
                        real_bal = float(data.get("user", {}).get("balance", 0.0))
                        demo_bal = float(data.get("user", {}).get("demo_balance", 50000.0))
                        return {
                            "success": True,
                            "ssid": ssid, "po_session": session,
                            "po_uid": str(uid), "account_id": str(uid),
                            "demo_balance": demo_bal, "real_balance": real_bal,
                        }

        return {"success": False, "error": "Session not found after HTTP login"}
    except Exception as e:
        log_error(f"_login_via_api error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# ── Method 2 — Playwright stealth browser ────────────────────────────────────

async def _playwright_auth(email: str, password: str, is_registration: bool) -> dict:
    """
    Uses playwright-stealth to open a headless Chrome, fill login/registration form,
    wait for cabinet redirect, then extracts demoSessionId from the cabinet page HTML.
    Falls back to WebSocket log interception if HTML extraction fails.
    """
    try:
        from playwright.async_api import async_playwright
        try:
            from playwright_stealth import stealth_async
            HAS_STEALTH = True
        except ImportError:
            HAS_STEALTH = False

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage", "--disable-gpu",
                    "--single-process", "--no-zygote",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars", "--window-size=1280,720",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )

            page = await context.new_page()

            if HAS_STEALTH:
                await stealth_async(page)

            await context.add_init_script("""
                Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
                Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
                window.chrome={runtime:{}};
                delete navigator.__proto__.webdriver;
            """)

            # Intercept WebSocket auth frames as a secondary extraction method
            captured_ssid = []

            async def handle_ws(ws):
                async def on_frame_sent(payload):
                    if isinstance(payload, str) and '"auth"' in payload and '"session"' in payload:
                        captured_ssid.append(payload)
                async def on_frame_received(payload):
                    if isinstance(payload, str) and '"auth"' in payload and '"session"' in payload:
                        captured_ssid.append(payload)
                ws.on("framesent", lambda f: asyncio.create_task(on_frame_sent(f.payload if hasattr(f,'payload') else str(f))))
                ws.on("framereceived", lambda f: asyncio.create_task(on_frame_received(f.payload if hasattr(f,'payload') else str(f))))

            page.on("websocket", handle_ws)

            target_url = (
                "https://pocketoption.com/en/registration/"
                if is_registration
                else "https://pocketoption.com/en/login/"
            )

            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)

            # Fill email
            for sel in ['input[name="email"]', 'input[type="email"]', '#email', '[placeholder*="email" i]']:
                try:
                    el = await page.wait_for_selector(sel, timeout=2000)
                    if el:
                        await el.fill(email)
                        break
                except Exception:
                    pass

            # Fill password
            pw_inputs = await page.query_selector_all('input[type="password"]')
            if pw_inputs:
                await pw_inputs[0].fill(password)

            # Fill confirm password (registration only)
            if is_registration and len(pw_inputs) >= 2:
                await pw_inputs[1].fill(password)

            # Check all checkboxes (agree to terms)
            for cb in await page.query_selector_all('input[type="checkbox"]'):
                try:
                    await cb.check()
                except Exception:
                    pass

            await page.wait_for_timeout(1000)

            # Click submit
            for sel in [
                'button[type="submit"]', 'input[type="submit"]',
                'button.btn-primary', 'form button:last-of-type',
                '[class*="register" i]', '[class*="login" i]',
            ]:
                try:
                    el = await page.wait_for_selector(sel, timeout=2000)
                    if el and await el.is_visible():
                        await el.click()
                        break
                except Exception:
                    pass

            # Wait for cabinet redirect
            try:
                await page.wait_for_url("**/cabinet/**", timeout=30000)
            except Exception:
                await page.wait_for_timeout(10000)

            if "/cabinet/" not in page.url:
                await browser.close()
                return {"success": False, "error": f"Did not reach cabinet. URL: {page.url}"}

            # Navigate to demo trading page to trigger WebSocket auth
            await page.goto(
                "https://pocketoption.com/en/cabinet/demo-quick-high-low/",
                wait_until="domcontentloaded", timeout=30000,
            )
            await page.wait_for_timeout(6000)

            # Get cookies and HTML
            all_cookies = await context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in all_cookies}
            html = await page.content()

            # Try user info API
            real_balance = 0.0
            demo_balance = 50000.0
            try:
                info = await page.evaluate("""
                    async () => {
                        try {
                            const r = await fetch('/api/user/info', {credentials:'include'});
                            return await r.json();
                        } catch(e) { return {}; }
                    }
                """)
                if isinstance(info, dict):
                    real_balance = float(info.get("balance", 0.0))
                    demo_balance = float(info.get("demo_balance", 50000.0))
            except Exception:
                pass

            await browser.close()

            # PRIMARY: extract from HTML
            session, uid = _extract_session_from_html(html)

            # SECONDARY: captured WebSocket auth frame
            if (not session or not uid) and captured_ssid:
                for raw in captured_ssid:
                    try:
                        # raw is like: 42["auth",{"session":"...","isDemo":1,"uid":N,...}]
                        m = re.search(r'42\["auth",(\{.*?\})\]', raw, re.DOTALL)
                        if m:
                            d = json.loads(m.group(1))
                            session = d.get("session", "")
                            uid = str(d.get("uid", ""))
                            if session and uid:
                                ssid = raw  # use the exact captured frame
                                return {
                                    "success": True,
                                    "ssid": ssid, "po_session": session,
                                    "po_uid": uid, "account_id": uid,
                                    "demo_balance": demo_balance,
                                    "real_balance": real_balance,
                                }
                    except Exception:
                        pass

            # TERTIARY: ci_session cookie
            if not session or not uid:
                ci = cookie_dict.get("ci_session", "")
                if ci:
                    session = urllib.parse.unquote(ci)
                uid = uid or cookie_dict.get("uid", cookie_dict.get("user_id", ""))

            if session and uid:
                ssid = _build_ssid(session, str(uid), is_demo=True)
                return {
                    "success": True,
                    "ssid": ssid, "po_session": session,
                    "po_uid": str(uid), "account_id": str(uid),
                    "demo_balance": demo_balance, "real_balance": real_balance,
                }

            return {"success": False, "error": "Could not extract session from browser"}

    except Exception as e:
        log_error(f"_playwright_auth error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# ── Method 3 — WebSocket registration attempt ─────────────────────────────────

async def _register_via_websocket(email: str, password: str) -> dict:
    try:
        import websockets

        ws_url = "wss://demo-api-eu.po.market/socket.io/?EIO=4&transport=websocket"
        headers = {
            "Origin": "https://pocketoption.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }

        async with websockets.connect(ws_url, additional_headers=headers) as ws:
            await ws.recv()           # 0{...}
            await ws.send("40")
            await ws.recv()           # 40{...}

            reg_data = json.dumps(["register", {
                "email": email, "password": password,
                "password_confirmation": password, "locale": "en",
            }])
            await ws.send(f"42{reg_data}")

            for _ in range(15):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    if isinstance(msg, str) and msg.startswith("42"):
                        data = json.loads(msg[2:])
                        event = data[0] if isinstance(data, list) else ""
                        if event in ["registered", "authenticated", "successauth"]:
                            payload = data[1] if len(data) > 1 else {}
                            session = payload.get("session_id") or payload.get("token") or payload.get("session", "")
                            uid = str(payload.get("user_id") or payload.get("id") or payload.get("uid", ""))
                            if session and uid:
                                ssid = _build_ssid(session, uid, is_demo=True)
                                return {
                                    "success": True,
                                    "ssid": ssid, "po_session": session,
                                    "po_uid": uid, "account_id": uid,
                                    "demo_balance": 50000.0, "real_balance": 0.0,
                                }
                except asyncio.TimeoutError:
                    continue
    except Exception as e:
        log_error(f"_register_via_websocket error: {e}")

    return {"success": False, "error": "WebSocket registration failed"}


# ── Public API ────────────────────────────────────────────────────────────────

async def create_pocket_option_account(email: str) -> dict:
    """
    Fully automatic account creation.
    User provides ONLY their email — bot generates password.
    Tries 3 methods in order; never asks user for manual steps.
    """
    password = _gen_password()
    log(f"Creating account for: {email}")

    methods = [
        ("HTTP API", lambda: _register_via_api(email, password)),
        ("Playwright", lambda: _playwright_auth(email, password, is_registration=True)),
        ("WebSocket", lambda: _register_via_websocket(email, password)),
    ]

    for name, method in methods:
        try:
            log(f"Trying {name} registration...")
            result = await method()
            if result.get("success"):
                log(f"✅ {name} registration succeeded!")
                result["email"] = email
                result["password"] = password
                return result
            else:
                log(f"❌ {name} registration failed: {result.get('error')}")
        except Exception as e:
            log_error(f"{name} registration exception: {e}", exc_info=True)
        await asyncio.sleep(2)

    return {
        "success": False,
        "error": "Registration failed. Please try a different email address.",
        "email": email,
        "password": password,
    }


async def login_pocket_option_account(email: str, password: str) -> dict:
    """
    Fully automatic login.
    Tries HTTP API first, then Playwright browser.
    """
    log(f"Logging in: {email}")

    methods = [
        ("HTTP API", lambda: _login_via_api(email, password)),
        ("Playwright", lambda: _playwright_auth(email, password, is_registration=False)),
    ]

    for name, method in methods:
        try:
            log(f"Trying {name} login...")
            result = await method()
            if result.get("success"):
                log(f"✅ {name} login succeeded!")
                result["email"] = email
                result["password"] = password
                return result
            else:
                log(f"❌ {name} login failed: {result.get('error')}")
        except Exception as e:
            log_error(f"{name} login exception: {e}", exc_info=True)
        await asyncio.sleep(2)

    return {
        "success": False,
        "error": "Login failed. Please check your email and password.",
    }


async def refresh_session(email: str, password: str) -> dict:
    """Re-login to get a fresh SSID. Used by session_manager auto-refresh."""
    return await login_pocket_option_account(email, password)
