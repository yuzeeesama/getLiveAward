from __future__ import annotations

MISSION_INFO_URL = "https://api.bilibili.com/x/activity_components/mission/info"
MISSION_RECEIVE_URL = "https://api.bilibili.com/x/activity_components/mission/receive"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
QRCODE_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QRCODE_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0"
)
WEB_LOCATION = "888.126558"

MISSION_INFO_RETRY_SECONDS = 30.0
MISSION_INFO_RETRY_INTERVAL = 1.0
LOGIN_POLL_TIMEOUT_SECONDS = 180.0
LOGIN_POLL_INTERVAL_SECONDS = 1.5

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]
