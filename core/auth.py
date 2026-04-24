from __future__ import annotations

import io
import time
import urllib.parse

import qrcode
import requests

from .constants import (
    DEFAULT_USER_AGENT,
    LOGIN_POLL_INTERVAL_SECONDS,
    LOGIN_POLL_TIMEOUT_SECONDS,
    QRCODE_GENERATE_URL,
    QRCODE_POLL_URL,
)
from .errors import BiliRewardError, LoginCancelledError
from .models import OptionalCancelCheck, OptionalLogCallback, OptionalQrCodeCallback, QrCodeData
from .storage import validate_cookies_dict


def get_login_qrcode(session: requests.Session) -> tuple[str, str]:
    response = session.get(
        QRCODE_GENERATE_URL,
        headers={"User-Agent": DEFAULT_USER_AGENT, "Referer": "https://www.bilibili.com"},
        timeout=10,
    )
    payload = response.json()
    if payload.get("code") != 0:
        raise BiliRewardError(f"获取登录二维码失败: {payload}")
    data = payload.get("data") or {}
    qrcode_url = data.get("url")
    qrcode_key = data.get("qrcode_key")
    if not qrcode_url or not qrcode_key:
        raise BiliRewardError("登录二维码返回内容不完整")
    return qrcode_url, qrcode_key


def make_qrcode_bytes(url: str) -> bytes:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def poll_login(
    qrcode_key: str,
    session: requests.Session,
    *,
    log_callback: OptionalLogCallback = None,
    cancel_check: OptionalCancelCheck = None,
) -> dict[str, str]:
    params = {"qrcode_key": qrcode_key}
    start = time.time()
    last_status: int | None = None

    while time.time() - start < LOGIN_POLL_TIMEOUT_SECONDS:
        if cancel_check is not None and cancel_check():
            raise LoginCancelledError("[登录] 已取消扫码登录")

        response = session.get(
            QRCODE_POLL_URL,
            params=params,
            headers={"User-Agent": DEFAULT_USER_AGENT, "Referer": "https://www.bilibili.com"},
            timeout=10,
        )
        payload = response.json()
        data = payload.get("data") or {}
        code = data.get("code")

        if code != last_status:
            last_status = code
            if log_callback is not None:
                if code == 86101:
                    log_callback("[登录] 等待扫码")
                elif code == 86090:
                    log_callback("[登录] 已扫码，等待手机确认")
                elif code == 86038:
                    raise BiliRewardError("[登录] 二维码已过期，请重试")
                elif code == 0:
                    log_callback("[登录] 扫码登录成功")
                else:
                    log_callback(f"[登录] 未知状态: code={code}, message={data.get('message', '')}")

        if code == 0:
            cookies = {cookie.name: cookie.value for cookie in session.cookies}
            redirect_url = data.get("url")
            if redirect_url:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query)
                for key, values in query.items():
                    if key not in cookies and values:
                        cookies[key] = values[0]
            return cookies

        time.sleep(LOGIN_POLL_INTERVAL_SECONDS)

    raise BiliRewardError("[登录] 扫码登录超时，请重试")


def login_and_get_cookies(
    *,
    log_callback: OptionalLogCallback = None,
    qr_callback: OptionalQrCodeCallback = None,
    cancel_check: OptionalCancelCheck = None,
) -> dict[str, str]:
    session = requests.Session()
    if log_callback is not None:
        log_callback("[登录] 正在生成扫码登录二维码")
    qrcode_url, qrcode_key = get_login_qrcode(session)
    qr_data = QrCodeData(
        login_url=qrcode_url,
        qrcode_key=qrcode_key,
        image_bytes=make_qrcode_bytes(qrcode_url),
    )
    if qr_callback is not None:
        qr_callback(qr_data)
    cookies = poll_login(
        qrcode_key,
        session,
        log_callback=log_callback,
        cancel_check=cancel_check,
    )
    validate_cookies_dict(cookies)
    return cookies
