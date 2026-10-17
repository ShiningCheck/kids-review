# -*- coding: utf-8 -*-
"""首次配置与环境安装脚本。

用法：
    python scripts/setup.py
    python scripts/setup.py --check
    python scripts/setup.py --config-dir D:/config --venv-dir D:/venv

脚本不读取真实 API Key，也不回显 Key。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"


def default_venv_dir() -> Path:
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "kids-review-editing" / "venv"
    root = os.environ.get("XDG_CACHE_HOME")
    if root:
        return Path(root) / "kids-review-editing" / "venv"
    return Path.home() / ".cache" / "kids-review-editing" / "venv"


def venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_venv(venv_dir: Path) -> Path:
    venv_dir.mkdir(parents=True, exist_ok=True)
    py = venv_python(venv_dir)
    if not py.exists():
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
        )
    return py


def packages_ok(py: Path) -> bool:
    probe = (
        "import requests, dotenv, imageio_ffmpeg, docx, PIL, numpy, scipy;"
        "print('OK')"
    )
    try:
        result = subprocess.run(
            [str(py), "-c", probe],
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and "OK" in result.stdout


def install_requirements(py: Path) -> None:
    subprocess.run(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(SKILL_DIR / "requirements.txt"),
        ],
        check=True,
    )


def copy_template(template: str, target: Path) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return False
    shutil.copy2(SKILL_DIR / template, target)
    return True


def api_key_from_env_file(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "ASR_API_KEY":
            return value.strip().strip('"').strip("'")
    return ""


def current_api_key() -> str:
    return os.getenv("ASR_API_KEY", "").strip() or api_key_from_env_file(env_path())


def print_summary(py: Path) -> None:
    print("")
    print("配置生成完成：")
    print(f"  CONFIG_DIR   = {config_dir()}")
    print(f"  ENV_PATH     = {env_path()}")
    print(f"  PROFILE_PATH = {profile_path()}")
    print(f"  PY           = {py}")
    print(f"  S            = {SCRIPTS_DIR}")
    print("")
    print("下一步：")
    print("  1. 编辑 .env，填写 ASR_API_KEY。")
    print("  2. 编辑 profile.json，填写孩子姓名/学校名等隐私词和编辑偏好。")
    print("  3. 在 PowerShell 中运行脚本前先设置：")
    print('       $env:PYTHONIOENCODING="utf-8"')
    print("")
    if sys.platform == "win32":
        print("Windows 示例：")
        print(f"  PY='{py.as_posix()}'")
        print(f"  S='{SCRIPTS_DIR.as_posix()}'")
        print('  $env:PYTHONIOENCODING="utf-8"')
        print("  & $PY $S/transcribe.py --help")


def main() -> int:
    global config_dir, env_path, profile_path

    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只检查，不安装")
    parser.add_argument("--config-dir", default=None, help="覆盖配置目录")
    parser.add_argument("--venv-dir", default=None, help="覆盖虚拟环境目录")
    args = parser.parse_args()

    if args.config_dir:
        os.environ["KIDS_REVIEW_CONFIG_DIR"] = str(Path(args.config_dir).expanduser())

    from config import config_dir as _config_dir
    from config import env_path as _env_path
    from config import profile_path as _profile_path

    config_dir = _config_dir
    env_path = _env_path
    profile_path = _profile_path

    venv_dir = Path(args.venv_dir).expanduser() if args.venv_dir else default_venv_dir()
    py = venv_python(venv_dir)

    if args.check:
        failures = []
        print(f"CONFIG_DIR   = {config_dir()}")
        print(f"ENV_PATH     = {env_path()}")
        print(f"PROFILE_PATH = {profile_path()}")
        print(f"VENV_PY      = {py}")

        env_template = SKILL_DIR / ".env.example"
        if not env_template.exists():
            print("ENV_TEMPLATE = MISSING")
            failures.append(".env")
        else:
            print("ENV_TEMPLATE = OK")

        profile_template = SKILL_DIR / "profile.example.json"
        if not profile_template.exists():
            print("PROFILE_TEMPLATE = MISSING")
            failures.append("profile.example.json")
        else:
            print("PROFILE_TEMPLATE = OK")

        if not profile_path().exists():
            print("PROFILE      = MISSING")
            failures.append("profile.json")
        else:
            print("PROFILE      = OK")

        if not py.exists():
            print("VENV         = MISSING")
            failures.append("venv")
        elif packages_ok(py):
            print("DEPENDENCIES = OK")
        else:
            print("DEPENDENCIES = MISSING")
            failures.append("dependencies")

        if current_api_key():
            print("ASR_API_KEY  = configured")
        else:
            print("ASR_API_KEY  = MISSING")
            failures.append("ASR_API_KEY")

        print("")
        if failures:
            print(f"请先补齐：{', '.join(failures)}")
            return 1
        print("ALL OK")
        return 0

    copy_template(".env.example", env_path())
    copy_template("profile.example.json", profile_path())
    try:
        py = ensure_venv(venv_dir)
        install_requirements(py)
    except (OSError, subprocess.CalledProcessError) as exc:
        print("")
        print(f"环境安装失败：{exc}")
        print("请检查 Python 版本和网络后重试。")
        return 1
    print_summary(py)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
