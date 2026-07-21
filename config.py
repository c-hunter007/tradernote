"""项目配置加载（dotenv + 默认值）。"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent

# 加载 .env 文件（若存在）
load_dotenv(BASE_DIR / ".env")


def _get_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _get_env_int(name: str, default: int) -> int:
    try:
        return int(_get_env(name, str(default)))
    except ValueError:
        return default


# 数据库路径（绝对路径）
DB_PATH = Path(_get_env("DB_PATH", "data/tradernote.db"))
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH

# 上传目录（绝对路径）
UPLOAD_DIR = Path(_get_env("UPLOAD_DIR", "uploads"))
if not UPLOAD_DIR.is_absolute():
    UPLOAD_DIR = BASE_DIR / UPLOAD_DIR

# 会话保持天数
SESSION_DAYS = _get_env_int("SESSION_DAYS", 30)

# SQLite 连接字符串
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 图片大小限制（单张 ≤ 3MB）
MAX_IMAGE_BYTES = 3 * 1024 * 1024


def ensure_dirs() -> None:
    """确保运行时所需目录存在。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
