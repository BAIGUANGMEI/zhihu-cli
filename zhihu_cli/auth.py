"""Authentication for Zhihu.

Strategy:
1. Try loading saved cookies from ~/.zhihu-cli/cookies.json
2. QR code login: API-based (no Playwright) — POST qrcode API, show QR in terminal, poll scan_info
3. Manual cookie: user provides cookie string directly

知乎登录网址: https://www.zhihu.com/signin
QR 登录 API: https://www.zhihu.com/api/v3/account/api/login/qrcode
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

from .config import (
    CONFIG_DIR,
    COOKIE_FILE,
    DEFAULT_HEADERS,
    REQUIRED_COOKIES,
    ZHIHU_BASE_URL,
    ZHIHU_LOGIN_URL,
    ZHIHU_OAUTH_CAPTCHA,
    ZHIHU_QRCODE_API,
)
from .display import console, print_error, print_hint, print_info, print_success, print_warning
from .exceptions import LoginError

logger = logging.getLogger(__name__)


def get_saved_cookie_string() -> str | None:
    """Load only saved cookies from local config file.

    This helper never triggers browser extraction and has no write side effects.
    """
    return _load_saved_cookies()


def get_cookie_string() -> str | None:
    """Try loading saved cookies. Returns cookie string or None."""
    cookie = _load_saved_cookies()
    if cookie:
        logger.info("Loaded saved cookies from %s", COOKIE_FILE)
        return cookie
    return None


def _load_saved_cookies() -> str | None:
    """Load cookies from saved file."""
    if not COOKIE_FILE.exists():
        return None

    try:
        data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
        cookies = data.get("cookies", {})
        if _has_required_cookies(cookies):
            return _dict_to_cookie_str(cookies)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to load saved cookies: %s", e)

    return None


def qrcode_login() -> str:
    """Login via QR code using API only (no Playwright).

    Calls POST /api/v3/account/api/login/qrcode to get token and link,
    displays the link as QR in terminal (qrcode lib), then polls
    scan_info until user scans and confirms; returns cookie string.
    """
    return _qrcode_login_api()


def _set_xsrf_header(session: requests.Session) -> None:
    """从当前会话 cookie 读取 _xsrf 并设置 x-xsrftoken 头，避免 403。"""
    xsrf = session.cookies.get("_xsrf")
    if xsrf:
        session.headers["x-xsrftoken"] = xsrf


def _qrcode_login_api() -> str:
    """QR code login using only requests + qrcode (no Playwright)."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    # 与浏览器一致，避免 403：Referer/Origin 必须为知乎站内
    session.headers["Referer"] = f"{ZHIHU_BASE_URL}/signin"
    session.headers["Origin"] = ZHIHU_BASE_URL
    session.headers["x-requested-with"] = "fetch"

    # 1. Get initial cookies (signin page)
    try:
        session.get(ZHIHU_LOGIN_URL, timeout=15)
    except requests.RequestException as e:
        raise LoginError(f"Failed to load login page: {e}") from e

    # 2. udid for d_c0, q_c1
    try:
        session.post(f"{ZHIHU_BASE_URL}/udid", json={}, timeout=10)
    except requests.RequestException:
        pass

    # 3. captcha 获取 capsion_ticket（扫码确认流程需要）
    try:
        session.get(ZHIHU_OAUTH_CAPTCHA, timeout=10)
    except requests.RequestException:
        pass

    # 4. Get QR code token and link (API 要求 POST，GET 会返回 405)
    _set_xsrf_header(session)
    try:
        r = session.post(ZHIHU_QRCODE_API, json={}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        raise LoginError(f"Failed to get QR code: {e}") from e

    token = data.get("token") or data.get("qrcode_token")
    link = data.get("link") or ""
    if not token or not link:
        raise LoginError("QR code API did not return token or link")

    # 5. Show QR in terminal (link is the URL to scan)
    print_info("请使用知乎 App 扫描下方二维码登录")
    console.print()
    if not _display_qr_text_in_terminal(link):
        print_hint(f"若终端无法显示二维码，请用手机浏览器打开: {link}")
    console.print()
    print_info("请在手机上点击「确认登录」…")

    # 6. Poll scan_info until login success (response sets z_c0 via Set-Cookie)
    scan_url = f"{ZHIHU_QRCODE_API}/{token}/scan_info"
    deadline = time.time() + 120  # 2 min
    use_post = False  # 若 GET 返回 405 则改用 POST
    poll_interval = 0.25  # 每 0.25 秒轮询，点完确认后更快提示成功
    while time.time() < deadline:
        time.sleep(poll_interval)
        _set_xsrf_header(session)
        try:
            if use_post:
                resp = session.post(scan_url, json={}, timeout=10)
            else:
                resp = session.get(scan_url, timeout=10)
            if resp.status_code == 405 and not use_post:
                use_post = True
                continue
            info = {}
            if resp.content:
                try:
                    info = resp.json()
                except ValueError:
                    pass
            # 扫码确认成功：状态码 200/201，且 (body 中 status 为 CONFIRMED 或 会话/响应 中已有 z_c0)
            if resp.status_code in (200, 201):
                status = (info.get("status") or info.get("login_status") or "").upper()
                if status in ("CONFIRMED", "LOGIN_SUCCESS", "SUCCESS"):
                    break
                # 服务端可能通过 Set-Cookie 写入 z_c0，或放在 body 里
                if session.cookies.get("z_c0"):
                    break
                for c in resp.cookies:
                    if c.name == "z_c0":
                        session.cookies.set(c.name, c.value, domain=c.domain or ".zhihu.com")
                        break
                if session.cookies.get("z_c0"):
                    break
            resp.raise_for_status()
        except requests.RequestException:
            continue

    # 7. 确认会话中已有 z_c0（scan_info 成功时由服务端 Set-Cookie）
    if not session.cookies.get("z_c0"):
        # 再请求一次需登录的页面，触发并接收完整 cookie
        try:
            session.get(f"{ZHIHU_BASE_URL}/api/v4/me", timeout=10)
        except requests.RequestException:
            pass

    # 8. Collect cookies from session
    cookie_dict = dict(session.cookies)

    if not REQUIRED_COOKIES.issubset(cookie_dict.keys()):
        raise LoginError("二维码登录超时或未完成确认（未获取到 z_c0）")

    cookie_str = _dict_to_cookie_str(cookie_dict)
    save_cookies(cookie_str)
    return cookie_str


def _render_qr_half_blocks(matrix: list[list[bool]]) -> str:
    """Render QR matrix using half-block characters (▀▄█)."""
    if not matrix:
        return ""

    border = 2
    width = len(matrix[0]) + border * 2
    padded = [[False] * width for _ in range(border)]
    for row in matrix:
        padded.append(([False] * border) + row + ([False] * border))
    padded.extend([[False] * width for _ in range(border)])

    chars = {
        (False, False): " ",
        (True, False): "▀",
        (False, True): "▄",
        (True, True): "█",
    }

    lines = []
    for y in range(0, len(padded), 2):
        top = padded[y]
        bottom = padded[y + 1] if y + 1 < len(padded) else [False] * width
        line = "".join(chars[(top[x], bottom[x])] for x in range(width))
        lines.append(line)
    return "\n".join(lines)


def _display_qr_text_in_terminal(qr_text: str) -> bool:
    """Render QR text as terminal half-block art."""
    try:
        import qrcode
    except ImportError:
        return False

    try:
        qr = qrcode.QRCode(border=0)
        qr.add_data(qr_text)
        qr.make(fit=True)
        console.print(_render_qr_half_blocks(qr.get_matrix()))
        return True
    except Exception:
        return False


def save_cookies(cookie_str: str):
    """Save cookies to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    cookies = cookie_str_to_dict(cookie_str)
    data = {"cookies": cookies}

    COOKIE_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    try:
        COOKIE_FILE.chmod(0o600)
    except OSError:
        logger.debug("Failed to set permissions on %s", COOKIE_FILE)
    logger.info("Cookies saved to %s", COOKIE_FILE)


def clear_cookies():
    """Remove saved cookies (for logout)."""
    removed = []
    if COOKIE_FILE.exists():
        COOKIE_FILE.unlink()
        removed.append(COOKIE_FILE.name)
    if removed:
        logger.info("Removed: %s", ", ".join(removed))
    return removed


def _has_required_cookies(cookies: dict) -> bool:
    return REQUIRED_COOKIES.issubset(cookies.keys())


def _dict_to_cookie_str(cookies: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def cookie_str_to_dict(cookie_str: str) -> dict:
    """Parse a cookie header string into a dict.

    Example: "z_c0=xxx; _xsrf=yyy" -> {"z_c0": "xxx", "_xsrf": "yyy"}
    """
    result = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            result[k.strip()] = v.strip()
    return result
