from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.cookiejar import Cookie, CookieJar
from typing import Optional

from .constants import (
    DEFAULT_USER_AGENT,
    MISSION_INFO_RETRY_INTERVAL,
    MISSION_INFO_RETRY_SECONDS,
    MISSION_INFO_URL,
    MISSION_RECEIVE_URL,
    MIXIN_KEY_ENC_TAB,
    NAV_URL,
    WEB_LOCATION,
)
from .errors import BiliCookieInvalidError, BiliRewardCancelledError, BiliRewardError
from .models import AwardInfo, ClaimExecutionControl, OptionalLogCallback


def format_api_failure(stage: str, code: object, message: object, *, detail: str = "") -> str:
    suffix = f", {detail}" if detail else ""
    return f"[{stage}] 失败: code={code}, message={message}{suffix}"


def format_cookies_text(cookies: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in cookies.items())


def is_cookie_invalid_error(error: BiliRewardError) -> bool:
    text = str(error)
    invalid_markers = (
        "code=-101",
        "code=61000",
        "账号未登录",
        "请先登录",
        "登录态",
        "Cookie 中缺少 bili_jct",
    )
    return any(marker in text for marker in invalid_markers)


def should_relogin_from_error(error: BiliRewardError) -> bool:
    return isinstance(error, BiliCookieInvalidError) or is_cookie_invalid_error(error)


class BiliRewardClient:
    def __init__(self, cookie_string: str, timeout: float = 10.0) -> None:
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.opener.addheaders = [
            ("User-Agent", DEFAULT_USER_AGENT),
            ("Referer", "https://www.bilibili.com/"),
        ]
        self._set_cookie_string(cookie_string)

    def _set_cookie_string(self, cookie_string: str) -> None:
        for part in cookie_string.split(";"):
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            name = name.strip()
            value = value.strip()
            if not name:
                continue
            cookie = Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=".bilibili.com",
                domain_specified=True,
                domain_initial_dot=True,
                path="/",
                path_specified=True,
                secure=False,
                expires=None,
                discard=True,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
            self.cookie_jar.set_cookie(cookie)

    def _request_json(
        self,
        url: str,
        data: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict:
        request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise BiliRewardError(f"HTTP {exc.code} 请求失败: {body}") from exc
        except urllib.error.URLError as exc:
            raise BiliRewardError(f"网络请求失败: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise BiliRewardError("接口返回了无法解析的 JSON") from exc

    def _get_wbi_keys(self) -> tuple[str, str]:
        payload = self._request_json(NAV_URL)
        data = payload.get("data") or {}
        wbi_img = data.get("wbi_img") or {}
        img_url = wbi_img.get("img_url")
        sub_url = wbi_img.get("sub_url")
        if not img_url or not sub_url:
            raise BiliRewardError("获取 WBI 密钥失败")
        img_key = img_url.rsplit("/", 1)[-1].split(".", 1)[0]
        sub_key = sub_url.rsplit("/", 1)[-1].split(".", 1)[0]
        return img_key, sub_key

    def ensure_logged_in(self) -> None:
        payload = self._request_json(NAV_URL)
        data = payload.get("data") or {}
        if not data.get("isLogin"):
            raise BiliCookieInvalidError("[Cookie] 当前登录态无效: NAV isLogin=false")
        self.get_csrf()

    def get_web_sign(self, params: Optional[dict[str, str]] = None) -> str:
        raw_params = dict(params or {})
        img_key, sub_key = self._get_wbi_keys()
        mixin_source = img_key + sub_key
        mixin_key = "".join(mixin_source[i] for i in MIXIN_KEY_ENC_TAB)[:32]
        raw_params["wts"] = str(int(time.time()))
        ordered = dict(sorted(raw_params.items(), key=lambda item: item[0]))
        sanitized = {
            key: "".join(ch for ch in value if ch not in "!'()*")
            for key, value in ordered.items()
        }
        query = urllib.parse.urlencode(sanitized)
        w_rid = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
        sanitized["w_rid"] = w_rid
        return urllib.parse.urlencode(sanitized)

    def get_csrf(self) -> str:
        for cookie in self.cookie_jar:
            if cookie.name == "bili_jct":
                return cookie.value
        raise BiliRewardError("Cookie 中缺少 bili_jct，无法提交领取请求")

    def get_award_info(self, task_id: str, *, log_callback: OptionalLogCallback = None) -> AwardInfo:
        deadline = time.monotonic() + MISSION_INFO_RETRY_SECONDS
        attempt = 0
        while True:
            attempt += 1
            query = self.get_web_sign({
                "task_id": task_id,
                "web_location": WEB_LOCATION,
            })
            payload = self._request_json(f"{MISSION_INFO_URL}?{query}")
            code = payload.get("code", -1)
            message = payload.get("message", "")
            if code == 0:
                data = payload.get("data") or {}
                reward_info = data.get("reward_info") or {}
                result = AwardInfo(
                    act_id=str(data.get("act_id") or ""),
                    act_name=str(data.get("act_name") or ""),
                    task_name=str(data.get("task_name") or ""),
                    award_name=str(reward_info.get("award_name") or ""),
                )
                if any(not value for value in (result.act_id, result.act_name, result.task_name, result.award_name)):
                    raise BiliRewardError("奖励信息字段不完整，无法继续领取")
                return result

            last_error = format_api_failure("领取-任务信息", code, message)
            if log_callback is not None:
                log_callback(last_error)
            if code != -702 or time.monotonic() >= deadline:
                raise BiliRewardError(last_error)
            remaining = max(0.0, deadline - time.monotonic())
            if log_callback is not None:
                log_callback(
                    f"[领取-任务信息] 重试: attempt={attempt}, wait=1.0s, remaining~={remaining:.0f}s"
                )
            time.sleep(MISSION_INFO_RETRY_INTERVAL)

    def claim_award(
        self,
        task_id: str,
        *,
        award_info: AwardInfo | None = None,
        thread_count: int = 2,
        max_retry: int = 120,
        retry_interval: float = 1.0,
        log_callback: OptionalLogCallback = None,
        claim_control: ClaimExecutionControl | None = None,
    ) -> tuple[AwardInfo, str]:
        award_info = award_info or self.get_award_info(task_id, log_callback=log_callback)
        form = {
            "task_id": task_id,
            "activity_id": award_info.act_id,
            "activity_name": award_info.act_name,
            "task_name": award_info.task_name,
            "reward_name": award_info.award_name,
            "gaia_vtoken": "",
            "receive_from": "missionPage",
            "csrf": self.get_csrf(),
        }

        stop_event = threading.Event()
        errors: list[str] = []
        errors_lock = threading.Lock()

        def worker(worker_id: int) -> str:
            for attempt in range(1, max_retry + 1):
                if claim_control is not None:
                    claim_control.check_cancelled()
                    claim_control.wait_if_paused()
                if stop_event.is_set():
                    raise BiliRewardError(f"worker-{worker_id} cancelled")
                try:
                    query = self.get_web_sign()
                    body = urllib.parse.urlencode(form).encode("utf-8")
                    payload = self._request_json(
                        f"{MISSION_RECEIVE_URL}?{query}",
                        data=body,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    code = payload.get("code", -1)
                    if code == 0:
                        data = payload.get("data") or {}
                        extra_info = data.get("extra_info") or {}
                        cdkey = extra_info.get("cdkey_content")
                        if not cdkey:
                            raise BiliRewardError("领取成功，但返回中缺少 cdkey_content")
                        stop_event.set()
                        return str(cdkey)
                    message = payload.get("message", "")
                    if code == -101 or "账号未登录" in str(message):
                        stop_event.set()
                        raise BiliCookieInvalidError(
                            format_api_failure(
                                "领取-提交",
                                code,
                                message,
                                detail=f"worker={worker_id}, attempt={attempt}",
                            )
                        )
                    if log_callback is not None:
                        log_callback(
                            format_api_failure(
                                "领取-提交",
                                code,
                                message,
                                detail=f"worker={worker_id}, attempt={attempt}",
                            )
                        )
                    with errors_lock:
                        errors.append(f"worker-{worker_id} attempt-{attempt}: code={code}, message={message}")
                except BiliCookieInvalidError:
                    raise
                except BiliRewardCancelledError:
                    stop_event.set()
                    raise
                except BiliRewardError as exc:
                    if log_callback is not None:
                        log_callback(f"[领取-提交] 异常: worker={worker_id}, attempt={attempt}, error={exc}")
                    with errors_lock:
                        errors.append(f"worker-{worker_id} attempt-{attempt}: {exc}")
                except Exception as exc:  # pragma: no cover
                    if log_callback is not None:
                        log_callback(
                            f"[领取-提交] 异常: worker={worker_id}, attempt={attempt}, "
                            f"error={type(exc).__name__}: {exc}"
                        )
                    with errors_lock:
                        errors.append(f"worker-{worker_id} attempt-{attempt}: {type(exc).__name__}: {exc}")
                if attempt < max_retry and not stop_event.is_set():
                    if claim_control is not None:
                        claim_control.check_cancelled()
                        claim_control.wait_if_paused()
                    time.sleep(retry_interval)
            raise BiliRewardError(f"worker-{worker_id} 超过最大重试次数")

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = [executor.submit(worker, index + 1) for index in range(thread_count)]
            try:
                for future in as_completed(futures):
                    try:
                        return award_info, future.result()
                    except BiliRewardCancelledError:
                        stop_event.set()
                        raise
                    except BiliCookieInvalidError:
                        raise
                    except BiliRewardError as exc:
                        if stop_event.is_set():
                            continue
                        with errors_lock:
                            errors.append(str(exc))
                raise BiliRewardError("领取失败，所有线程都未成功")
            finally:
                stop_event.set()
                for future in futures:
                    future.cancel()
