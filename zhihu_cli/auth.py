"""Authentication for Zhihu.

Strategy:
1. Try loading saved cookies from ~/.zhihu-cli/cookies.json
2. Fallback: QR code login via Playwright browser automation
3. Manual cookie: user provides cookie string directly

知乎登录网址: https://www.zhihu.com/signin
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .config import CONFIG_DIR, COOKIE_FILE, DEFAULT_USER_AGENT, REQUIRED_COOKIES, ZHIHU_LOGIN_URL
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
    """Login via QR code using Playwright browser automation.

    Opens Zhihu login page, displays QR code in terminal,
    and waits for user to scan with Zhihu app.
    """
    import tempfile

    from playwright.sync_api import sync_playwright

    print_info("启动二维码登录…")
    console.print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=DEFAULT_USER_AGENT)
        page = context.new_page()

        # Navigate to Zhihu login page
        page.goto(
            ZHIHU_LOGIN_URL,
            wait_until="domcontentloaded",
            timeout=30000,
        )
        time.sleep(3)

        # Try to switch to QR code login tab
        _ensure_qr_login_tab(page)
        time.sleep(2)

        # Display QR code in terminal
        console.print()
        print_info("Scan the QR code below with the Zhihu app")
        console.print()
        qr_path = Path(tempfile.mkdtemp()) / "zhihu_qrcode.png"

        rendered = False
        qr_text = _extract_qr_text_from_page(page)
        if qr_text:
            rendered = _display_qr_text_in_terminal(qr_text)
            if not rendered:
                logger.debug("qrcode package unavailable; falling back to image display")

        if not rendered:
            _capture_qr_image(page, qr_path)
            _display_image_in_terminal(qr_path)

        # Record initial cookies before scan
        initial_cookies = context.cookies()
        initial_z_c0 = ""
        for c in initial_cookies:
            if c["name"] == "z_c0" and "zhihu" in c.get("domain", ""):
                initial_z_c0 = c["value"]

        # Poll for login completion
        console.print()
        print_info("Waiting for QR code scan…")
        for i in range(120):
            time.sleep(2)
            cookies = context.cookies()
            cookie_dict = {
                c["name"]: c["value"]
                for c in cookies
                if "zhihu" in c.get("domain", "")
            }

            current_z_c0 = cookie_dict.get("z_c0", "")

            # Check if page redirected away from login (successful login)
            current_url = page.url
            login_success = (
                (current_z_c0 and current_z_c0 != initial_z_c0)
                or ("signin" not in current_url and current_z_c0)
            )

            if login_success:
                print_success("Login successful")
                cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
                save_cookies(cookie_str)
                # Clean up temp file
                try:
                    if qr_path.exists():
                        qr_path.unlink()
                except Exception:
                    pass
                browser.close()
                return cookie_str

            if i % 15 == 14:
                print_info("Still waiting…")

        browser.close()
        raise LoginError("二维码登录超时（等待超过 4 分钟）")


def _ensure_qr_login_tab(page):
    """Switch to QR login tab if another login mode is active."""
    selectors = [
        'text=二维码登录',
        'text=扫码登录',
        '[class*="QRCode"]',
        'button:has-text("二维码")',
        'button:has-text("扫码")',
        'div:has-text("二维码登录")',
    ]
    for sel in selectors:
        el = page.query_selector(sel)
        if not el:
            continue
        try:
            el.click(force=True)
            return
        except Exception:
            continue


def _extract_qr_text_from_page(page) -> str:
    """Try to extract QR code URL/text from page elements."""
    try:
        qr_raw = page.evaluate(
            """() => {
                const selectors = [
                    'img[class*="qrcode"]',
                    'img[class*="QRCode"]',
                    'img[alt*="二维码"]',
                    'img[alt*="qrcode"]',
                    '.qr-code img',
                    'canvas[class*="qr"]',
                ];
                for (const sel of selectors) {
                    for (const el of document.querySelectorAll(sel)) {
                        const src = el.getAttribute("src") || "";
                        if (src && src.startsWith("http")) return src;
                        const dataUrl = el.getAttribute("data-url") || "";
                        if (dataUrl) return dataUrl;
                    }
                }
                return "";
            }"""
        )
    except Exception:
        return ""

    if isinstance(qr_raw, str) and qr_raw.strip():
        candidate = qr_raw.strip()
        if candidate.startswith("data:image/"):
            return ""
        return candidate
    return ""


def _capture_qr_image(page, qr_path: Path):
    """Capture QR image from page as screenshot."""
    qr_selectors = [
        'img[class*="qrcode"]',
        'img[class*="QRCode"]',
        'img[alt*="二维码"]',
        'canvas[class*="qr"]',
        ".qr-code img",
        ".QRCode",
    ]
    for sel in qr_selectors:
        el = page.query_selector(sel)
        if not el:
            continue
        try:
            el.screenshot(path=str(qr_path))
            return
        except Exception:
            continue

    # Try login container
    login_selectors = [
        ".Login-content",
        '[class*="login"]',
        ".SignIn-content",
    ]
    for sel in login_selectors:
        el = page.query_selector(sel)
        if not el:
            continue
        try:
            el.screenshot(path=str(qr_path))
            return
        except Exception:
            continue

    # Fallback: full page screenshot
    page.screenshot(path=str(qr_path), full_page=False)


def _display_image_in_terminal(image_path: Path):
    """Display an image in terminal or open with system viewer."""
    import base64
    import os
    import subprocess
    import sys

    term_program = os.getenv("TERM_PROGRAM", "")
    term = os.getenv("TERM", "")
    supports_inline = (
        term_program in {"iTerm.app", "WezTerm"}
        or "kitty" in term
        or bool(os.getenv("KITTY_WINDOW_ID"))
    )

    if supports_inline:
        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("ascii")
            osc = f"\033]1337;File=inline=1;preserveAspectRatio=1;width=40:{image_data}\a"
            sys.stdout.write(osc)
            sys.stdout.write("\n")
            sys.stdout.flush()
            return
        except Exception:
            pass

    print_info(f"QR code saved to: {image_path}")
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(image_path)])
        elif sys.platform == "win32":
            os.startfile(str(image_path))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(image_path)])
    except Exception:
        print_hint(f"Open manually: {image_path}")


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
