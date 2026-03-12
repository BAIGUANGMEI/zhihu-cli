"""Authentication for Zhihu.

Strategy:
1. Try loading saved cookies from ~/.zhihu-cli/cookies.json
2. QR code login: API-based (no Playwright) — POST qrcode API, show QR in terminal, poll scan_info
3. Manual cookie: user provides cookie string directly

知乎登录网址: https://www.zhihu.com/signin
QR 登录 API: https://www.zhihu.com/api/v3/account/api/login/qrcode
轮询扫码状态（官方）: https://www.zhihu.com/api/v3/account/api/login/qrcode/{token}/scan_info
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
    get_browser_headers,
    QRCODE_IMAGE_PATH,
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


def _apply_cookies_from_scan_info(
    session: requests.Session, info: dict, resp: requests.Response
) -> None:
    """从 scan_info 响应 body 或 Set-Cookie 中解析 cookie 并写入 session，避免漏检导致轮询超时。"""
    # body 中可能带 cookie 字符串或 z_c0 字段
    cookie_str = info.get("cookie") or info.get("cookies")
    if isinstance(cookie_str, str) and "z_c0" in cookie_str:
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                name, value = name.strip(), value.strip()
                if name:
                    session.cookies.set(name, value, domain=".zhihu.com")
    if info.get("z_c0"):
        session.cookies.set("z_c0", str(info.get("z_c0")), domain=".zhihu.com")
    # 确保响应头里的 Set-Cookie 被 session 吸收（requests 通常会自动，此处再补一次）
    for c in resp.cookies:
        session.cookies.set(c.name, c.value, domain=c.domain or ".zhihu.com")


def _qrcode_login_api() -> str:
    """QR code login using only requests + qrcode (no Playwright)."""
    session = requests.Session()
    session.headers.update(get_browser_headers())
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

    # 5. Save QR as image for AI Agent (e.g. OpenClaw) to send to user, then show in terminal
    _save_qrcode_image(link)

    print_info("请使用知乎 App 扫描下方二维码登录")
    console.print()
    if not _display_qr_text_in_terminal(link):
        print_hint(f"若终端无法显示二维码，请用手机浏览器打开: {link}")
    console.print()
    print_info("请在手机上点击「确认登录」…")

    # 6. Poll scan_info until login success (官方: .../qrcode/{token}/scan_info)
    # 403 PERMISSION_ERROR 常见原因：Cookie 不完整、缺少 x-xsrftoken、或请求头被拒（需与浏览器一致）
    scan_url = f"{ZHIHU_QRCODE_API}/{token}/scan_info"
    deadline = time.time() + 120  # 2 min
    poll_interval = 0.15  # 约每 0.15 秒轮询，点完确认后更快得到结果
    # 轮询前确保有 _xsrf（与 x-xsrftoken 头一致），缺则补一次登录页
    if not session.cookies.get("_xsrf"):
        try:
            session.get(ZHIHU_LOGIN_URL, timeout=10)
            _set_xsrf_header(session)
        except requests.RequestException:
            pass
    # scan_info 轮询追加 sec-fetch-* 和签名头（UA/sec-ch-ua 已由 get_browser_headers() 统一）
    session.headers["Referer"] = f"{ZHIHU_BASE_URL}/signin?next=%2F"
    session.headers["Accept"] = "*/*"
    session.headers["sec-fetch-dest"] = "empty"
    session.headers["sec-fetch-mode"] = "cors"
    session.headers["sec-fetch-site"] = "same-origin"
    session.headers["x-requested-with"] = "fetch"
    session.headers["x-zse-93"] = "101_3_3.0"
    while time.time() < deadline:
        time.sleep(poll_interval)
        _set_xsrf_header(session)
        try:
            resp = session.get(scan_url, timeout=10)
            info = {}
            if resp.content:
                try:
                    info = resp.json()
                except ValueError:
                    pass
            # 轮询 scan_info 官方约定：
            # - status: 0 → 未扫码，继续轮询
            # - status: 1 → 已扫码、未点确认，继续轮询
            # - 返回 access_token / user_id → 用户已点确认，登录成功
            if resp.status_code in (200, 201):
                api_status = info.get("status")
                if api_status is not None and api_status == 0:
                    # 未扫码
                    pass
                elif api_status is not None and api_status == 1:
                    # 已扫码未确认，继续轮询
                    pass
                elif info.get("access_token") or info.get("user_id") is not None:
                    # 用户已点确认，接口返回 token/user_id，登录成功
                    break
                else:
                    # 兼容其他返回格式
                    status_str = (info.get("login_status") or "").strip().upper()
                    if status_str in ("CONFIRMED", "LOGIN_SUCCESS", "SUCCESS", "OK", "LOGGED_IN"):
                        break
                    if info.get("success") is True or info.get("logged_in") is True:
                        break
                # 会话或响应中已有 z_c0 也视为成功
                if session.cookies.get("z_c0"):
                    break
                for c in resp.cookies:
                    if c.name == "z_c0":
                        session.cookies.set(c.name, c.value, domain=c.domain or ".zhihu.com")
                        break
                if session.cookies.get("z_c0"):
                    break
                _apply_cookies_from_scan_info(session, info, resp)
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


def _save_qrcode_image(qr_text: str) -> None:
    """Save QR code as PNG for AI Agent to send to user (e.g. OpenClaw)."""
    try:
        import qrcode
    except ImportError:
        return
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        img = qrcode.make(qr_text)
        img.save(QRCODE_IMAGE_PATH)
        print_hint(f"二维码已保存至: [bold]{QRCODE_IMAGE_PATH}[/bold]（AI Agent 可读取并发送给用户扫码）")
    except Exception as e:
        logger.debug("Failed to save QR code image: %s", e)


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
