"""用户管理服务。"""
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.password import hash_password
from database.models import User


@dataclass
class UserDTO:
    id: int
    username: str
    role: str
    is_active: bool
    created_by: Optional[int]
    created_by_username: Optional[str]


def _to_dto(user: User, creator_username: Optional[str] = None) -> UserDTO:
    return UserDTO(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_by=user.created_by,
        created_by_username=creator_username,
    )


def list_users(session: Session) -> list[UserDTO]:
    """返回所有用户。"""
    users = session.query(User).order_by(User.id).all()
    creator_ids = {u.created_by for u in users if u.created_by}
    creators: dict[int, str] = {}
    if creator_ids:
        rows = session.query(User).filter(User.id.in_(creator_ids)).all()
        creators = {r.id: r.username for r in rows}
    return [
        _to_dto(u, creators.get(u.created_by) if u.created_by else None)
        for u in users
    ]


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.query(User).filter_by(username=username.strip()).first()


def create_user(
    session: Session,
    username: str,
    password: str,
    role: str,
    creator_id: int,
) -> User:
    """创建普通用户/管理员账号。"""
    if role not in ("admin", "user"):
        raise ValueError("role 必须为 admin 或 user")
    if get_user_by_username(session, username):
        raise ValueError(f"用户名 {username} 已存在")
    user = User(
        username=username.strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        created_by=creator_id,
    )
    session.add(user)
    session.flush()
    return user


def reset_password(session: Session, user_id: int, new_password: str) -> None:
    user = session.get(User, user_id)
    if not user:
        raise ValueError("用户不存在")
    user.password_hash = hash_password(new_password)


def toggle_active(session: Session, user_id: int) -> bool:
    """切换启用/禁用状态，返回新状态。"""
    user = session.get(User, user_id)
    if not user:
        raise ValueError("用户不存在")
    user.is_active = not user.is_active
    session.flush()
    return user.is_active


def set_role(session: Session, user_id: int, role: str) -> None:
    if role not in ("admin", "user"):
        raise ValueError("role 必须为 admin 或 user")
    user = session.get(User, user_id)
    if not user:
        raise ValueError("用户不存在")
    user.role = role
    session.flush()


def count_admins(session: Session) -> int:
    return session.query(User).filter_by(role="admin", is_active=True).count()
