"""Configuration and path management for zhihu-cli."""

from __future__ import annotations

from pathlib import Path

# Application directories
CONFIG_DIR = Path.home() / ".zhihu-cli"
COOKIE_FILE = CONFIG_DIR / "cookies.json"
# QR code image path for AI Agent (e.g. OpenClaw) to send to user for scan login
QRCODE_IMAGE_PATH = CONFIG_DIR / "login_qrcode.png"

# z_c0 is the main authentication token for Zhihu
REQUIRED_COOKIES = frozenset({"z_c0"})

# Zhihu URLs
ZHIHU_BASE_URL = "https://www.zhihu.com"
ZHIHU_API_V4 = "https://www.zhihu.com/api/v4"
ZHIHU_API_V3 = "https://www.zhihu.com/api/v3"
ZHIHU_ZHUANLAN_API = "https://zhuanlan.zhihu.com/api"
ZHIHU_IMAGE_API = "https://api.zhihu.com/images"
ZHIHU_CONTENT_PUBLISH_URL = f"{ZHIHU_API_V4}/content/publish"
ZHIHU_CONTENT_DRAFTS_URL = f"{ZHIHU_API_V4}/content/drafts"
ZHIHU_OSS_UPLOAD_URL = "https://zhihu-pics-upload.zhimg.com"
ZHIHU_LOGIN_URL = "https://www.zhihu.com/signin"
# QR code login (no Playwright): get token/link, then poll scan_info
ZHIHU_QRCODE_API = f"{ZHIHU_API_V3}/account/api/login/qrcode"
# 防 CAPTCHA / 验证码（v2 登录用）
ZHIHU_OAUTH_CAPTCHA = f"{ZHIHU_API_V3}/oauth/captcha/v2?type=captcha_sign_in"

# HTTP defaults
DEFAULT_TIMEOUT = 15

# 全局统一 Chrome 版本号，UA / sec-ch-ua / sec-fetch-* 均从此派生，避免指纹矛盾
CHROME_VERSION = "145"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/{CHROME_VERSION}.0.0.0 Safari/537.36"
)


def get_browser_headers() -> dict[str, str]:
    """返回与浏览器一致的请求头（UA + sec-ch-ua 统一为 Chrome/{CHROME_VERSION}）。"""
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{ZHIHU_BASE_URL}/",
        "sec-ch-ua": (
            f'"Not:A-Brand";v="99", '
            f'"Google Chrome";v="{CHROME_VERSION}", '
            f'"Chromium";v="{CHROME_VERSION}"'
        ),
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
