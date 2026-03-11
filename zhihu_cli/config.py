"""Configuration and path management for zhihu-cli."""

from __future__ import annotations

from pathlib import Path

# Application directories
CONFIG_DIR = Path.home() / ".zhihu-cli"
COOKIE_FILE = CONFIG_DIR / "cookies.json"

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
ZHIHU_OAUTH_CAPTCHA = f"{ZHIHU_API_V3}/oauth/captcha?lang=cn"

# HTTP defaults
DEFAULT_TIMEOUT = 15
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Referer": f"{ZHIHU_BASE_URL}/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
