"""交互式初始化首个管理员账号。

使用方法：
    python -m scripts.init_admin

或直接运行：
    python scripts/init_admin.py

支持参数：
    --reset-password <username>   重置指定管理员的密码
"""
import argparse
import getpass
import sys

from auth.password import hash_password, verify_password
from database.db import get_session
from database.init_db import init_db
from database.models import User


def _read_username(prompt: str = "管理员用户名: ") -> str:
    while True:
        username = input(prompt).strip()
        if not username:
            print("用户名不能为空，请重新输入。")
            continue
        if len(username) > 64:
            print("用户名过长（最多 64 字符），请重新输入。")
            continue
        return username


def _read_password(confirm: bool = True) -> str:
    while True:
        password = getpass.getpass("密码: ")
        if len(password) < 6:
            print("密码至少 6 位，请重新输入。")
            continue
        if confirm:
            password2 = getpass.getpass("确认密码: ")
            if password != password2:
                print("两次输入不一致，请重新输入。")
                continue
        return password


def create_admin() -> None:
    """交互式创建首个管理员。"""
    init_db()

    with get_session() as session:
        existing_admin = session.query(User).filter_by(role="admin").first()
        if existing_admin:
            print(f"已存在管理员账号：{existing_admin.username}")
            print("如需创建新管理员，请登录应用后通过管理后台操作；")
            print("如需重置密码，请使用 --reset-password 参数。")
            return

        print("=== 创建首个管理员账号 ===")
        username = _read_username()
        # 检查用户名是否已存在（即使不是 admin）
        if session.query(User).filter_by(username=username).first():
            print(f"用户名 {username} 已存在，无法创建。")
            return
        password = _read_password()
        user = User(
            username=username,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
            created_by=None,
        )
        session.add(user)
        session.flush()
        print(f"\n管理员账号创建成功：{username} (id={user.id})")
        print("现在可以使用该账号登录应用。")


def reset_password(username: str) -> None:
    """重置指定管理员的密码。"""
    init_db()

    with get_session() as session:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            print(f"用户 {username} 不存在。")
            return
        if user.role != "admin":
            print(f"用户 {username} 不是管理员，无法通过此脚本重置密码。")
            return

        # 二次确认
        confirm = input(f"确认重置管理员 {username} 的密码？(y/N): ").strip().lower()
        if confirm != "y":
            print("已取消。")
            return

        # 校验旧密码（增强安全性）
        old_password = getpass.getpass("当前密码（验证身份）: ")
        if not verify_password(old_password, user.password_hash):
            print("当前密码错误，操作已取消。")
            return

        new_password = _read_password()
        user.password_hash = hash_password(new_password)
        print(f"管理员 {username} 的密码已重置。")


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化首个管理员账号或重置密码")
    parser.add_argument(
        "--reset-password",
        metavar="USERNAME",
        help="重置指定管理员的密码",
    )
    args = parser.parse_args()

    if args.reset_password:
        reset_password(args.reset_password)
    else:
        create_admin()
    return 0


if __name__ == "__main__":
    sys.exit(main())
