# -*- coding: utf-8 -*-
"""kids-review-editing 的用户级配置读取。

配置目录默认放在用户目录，避免更新/重装 skill 时覆盖个人设置：
  Windows: %APPDATA%\\kids-review-editing
  macOS:   ~/Library/Application Support/kids-review-editing
  Linux:   $XDG_CONFIG_HOME/kids-review-editing，否则 ~/.config/kids-review-editing

可通过环境变量 KIDS_REVIEW_CONFIG_DIR 覆盖。
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path


DEFAULT_PROFILE = {
    "privacy": {
        "child_names": [],
        "english_names": [],
        "school_names": [],
        "classmate_names": [],
        "other_sensitive": [],
    },
    "media": {
        "source_dirs": [],
        "output_root": "",
        "organize_by_date": True,
    },
    "editing": {
        "plain_transcript": True,
        "privacy_mode": "beep",
        "pitch_factor": 1.3,
        "denoise": "light",
        "loudnorm": True,
        "docx_font": "微软雅黑",
        "docx_body_pt": 11,
    },
    "video": {
        "title_line1": "我的一年级",
        "title_line2": "第一学期",
        "intro_seconds": 6.0,
        "resolution": "1440x1080",
        "crf": "20",
        "cover_font": "",
        "subtitle_font": "YouZiKuLongCang",
        "subtitle_font_size": 74,
        "subtitle_outline": 6,
        "subtitle_shadow": 2,
        "subtitle_margin_v": 46,
        "subtitle_max_chars": 15,
    },
}


def _default_config_dir() -> Path:
    if sys.platform == "win32":
        root = os.environ.get("APPDATA")
        if root:
            return Path(root) / "kids-review-editing"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "kids-review-editing"
    root = os.environ.get("XDG_CONFIG_HOME")
    if root:
        return Path(root) / "kids-review-editing"
    return Path.home() / ".config" / "kids-review-editing"


def config_dir() -> Path:
    override = os.environ.get("KIDS_REVIEW_CONFIG_DIR", "").strip()
    return Path(override).expanduser() if override else _default_config_dir()


def env_path() -> Path:
    return config_dir() / ".env"


def profile_path() -> Path:
    return config_dir() / "profile.json"


def load_env() -> None:
    """进程环境变量优先；.env 只补全未设置项。"""
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=env_path(), override=False)


def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_profile() -> dict:
    path = profile_path()
    if not path.exists():
        return copy.deepcopy(DEFAULT_PROFILE)
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return copy.deepcopy(DEFAULT_PROFILE)
    if not isinstance(raw, dict):
        return copy.deepcopy(DEFAULT_PROFILE)
    return _deep_merge(DEFAULT_PROFILE, raw)


def privacy_terms(profile: dict | None = None) -> list[str]:
    """收集 profile 中所有需要自动遮盖的隐私词。"""
    profile = profile or load_profile()
    privacy = profile.get("privacy", {})
    terms: list[str] = []
    for key in (
        "child_names",
        "english_names",
        "school_names",
        "classmate_names",
        "other_sensitive",
    ):
        for term in privacy.get(key, []):
            term = str(term).strip()
            if term and term not in terms:
                terms.append(term)
    return terms


def privacy_beep_terms(profile: dict | None = None) -> list[str]:
    """自动用于 --pitch-words 的隐私词。

    同学名和家庭敏感信息现在也进入默认哔声列表，作为整句删除失败时的兜底；
    工作流仍应优先整句删除涉及同学或家庭安排的句子。
    """
    return privacy_terms(profile)


def mask_privacy_text(
    text: str,
    profile: dict | None = None,
    replacement: str = "哔",
    terms: list[str] | None = None,
) -> str:
    """把隐私词替换成占位符，用于字幕等对外文本，与音频哔声保持一致。"""
    result = text
    term_list = list(terms) if terms is not None else privacy_terms(profile)
    for term in sorted(term_list, key=len, reverse=True):
        if not term:
            continue
        if term.isascii():
            result = re.sub(re.escape(term), replacement, result, flags=re.IGNORECASE)
        else:
            result = result.replace(term, replacement)
    return result


CONFIG_DIR = config_dir()
ENV_PATH = env_path()
PROFILE_PATH = profile_path()
