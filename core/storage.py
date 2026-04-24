from __future__ import annotations

import json
import os
import time
from typing import Optional

from .errors import BiliRewardError
from .models import RuntimePaths


def get_runtime_paths(base_dir: Optional[str] = None) -> RuntimePaths:
    root_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(root_dir, "data")
    logs_dir = os.path.join(data_dir, "logs")
    return RuntimePaths(
        data_dir=data_dir,
        logs_dir=logs_dir,
        cookie_file=os.path.join(data_dir, "bilibili_cookie.json"),
        log_file=os.path.join(logs_dir, "claim_live_reward.log"),
    )


def ensure_runtime_dirs(paths: RuntimePaths) -> None:
    os.makedirs(paths.data_dir, exist_ok=True)
    os.makedirs(paths.logs_dir, exist_ok=True)


def validate_cookies_dict(cookies: dict[str, str]) -> None:
    required_keys = ("SESSDATA", "bili_jct")
    missing_keys = [key for key in required_keys if not cookies.get(key)]
    if missing_keys:
        raise BiliRewardError(f"[Cookie] 缺少关键字段: {', '.join(missing_keys)}")


def save_cookie_file(cookie_file: str, cookies: dict[str, str]) -> None:
    validate_cookies_dict(cookies)
    payload = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cookies": cookies,
    }
    with open(cookie_file, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def load_cookie_file(cookie_file: str) -> Optional[dict[str, str]]:
    if not os.path.exists(cookie_file):
        return None

    try:
        with open(cookie_file, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None

    cookies = payload.get("cookies")
    if not isinstance(cookies, dict):
        return None

    normalized: dict[str, str] = {}
    for key, value in cookies.items():
        if isinstance(key, str) and isinstance(value, str):
            normalized[key] = value

    try:
        validate_cookies_dict(normalized)
    except BiliRewardError:
        return None
    return normalized
