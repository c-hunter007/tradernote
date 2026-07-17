"""分析结论服务：CRUD + 多图上传/存储/读取/删除。"""
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import MAX_IMAGE_BYTES, UPLOAD_DIR
from database.models import AnalysisImage, AnalysisNote, NoteComment, PoolStock, User

# ============================================================
# DTO
# ============================================================


@dataclass
class AnalysisNoteDTO:
    id: int
    pool_stock_id: int
    user_id: int
    username: str
    content: str
    created_at: datetime
    image_paths: list[str]  # 相对路径列表
    comment_count: int = 0


# ============================================================
# 图片处理工具
# ============================================================

# 允许的图片 MIME 类型 -> 扩展名映射
_MIME_TO_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def _note_dir(user_id: int, note_id: int) -> Path:
    """获取某条 note 的图片存储目录（绝对路径）。"""
    return UPLOAD_DIR / str(user_id) / str(note_id)


def _to_relative(path: Path) -> str:
    """将绝对路径转为相对于 UPLOAD_DIR 的路径。"""
    return str(path.relative_to(UPLOAD_DIR))


def _to_absolute(relative_path: str) -> Path:
    """将相对路径转为绝对路径。"""
    return UPLOAD_DIR / relative_path


def validate_image_file(uploaded_file) -> tuple[bool, str]:
    """校验图片：大小 ≤ 3MB + PIL 可加载。

    Args:
        uploaded_file: streamlit 的 UploadedFile 对象
    Returns:
        (ok, error_msg) 元组，校验通过 error_msg 为空字符串
    """
    if uploaded_file is None:
        return False, "文件为空"

    # 大小校验
    size = getattr(uploaded_file, "size", None)
    if size is None:
        # 兼容性：尝试读取后获取大小
        data = uploaded_file.getvalue()
        size = len(data)
    if size > MAX_IMAGE_BYTES:
        return False, f"图片大小 {(size / 1024 / 1024):.2f}MB 超过 3MB 限制"

    # MIME 类型校验
    mime = getattr(uploaded_file, "type", None)
    if mime and mime not in _MIME_TO_EXT:
        return False, f"不支持的图片类型：{mime}"

    # PIL 加载验证（防止伪装扩展名）
    try:
        data = uploaded_file.getvalue()
        import io
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        return True, ""
    except Exception:
        return False, "文件不是有效的图片"


def save_uploaded_image(uploaded_file, user_id: int, note_id: int) -> str:
    """保存上传的图片到本地，返回相对路径。

    - 文件名：uuid.uuid4().hex
    - 扩展名：根据 uploaded_file.type 推断（如 image/png → .png）
    - 磁盘错误（磁盘满、权限不足）抛出 ValueError，让上层统一处理
    """
    mime = getattr(uploaded_file, "type", None) or "image/png"
    ext = _MIME_TO_EXT.get(mime, ".png")
    filename = f"{uuid.uuid4().hex}{ext}"

    note_dir = _note_dir(user_id, note_id)
    abs_path = note_dir / filename

    try:
        note_dir.mkdir(parents=True, exist_ok=True)
        data = uploaded_file.getvalue()
        with open(abs_path, "wb") as f:
            f.write(data)
    except OSError as e:
        raise ValueError(f"图片保存失败：{e}") from e

    return _to_relative(abs_path)


def _delete_image_file(relative_path: str) -> None:
    """删除本地图片文件（忽略错误）。"""
    try:
        abs_path = _to_absolute(relative_path)
        # 安全检查：确保路径在 UPLOAD_DIR 内（防止路径穿越）
        abs_path.resolve().relative_to(UPLOAD_DIR.resolve())
        if abs_path.exists():
            abs_path.unlink()
    except (ValueError, OSError):
        pass


def _delete_note_dir_if_empty(user_id: int, note_id: int) -> None:
    """删除空的 note 目录（容错）。"""
    try:
        note_dir = _note_dir(user_id, note_id)
        if note_dir.exists() and not any(note_dir.iterdir()):
            note_dir.rmdir()
    except OSError:
        pass


# ============================================================
# 查询
# ============================================================


def list_notes(session: Session, pool_stock_id: int) -> list[AnalysisNoteDTO]:
    """列出某只 PoolStock 的分析结论（按时间倒序）。"""
    rows = (
        session.query(AnalysisNote, User)
        .join(User, AnalysisNote.user_id == User.id)
        .filter(AnalysisNote.pool_stock_id == pool_stock_id)
        .order_by(AnalysisNote.created_at.desc())
        .all()
    )
    if not rows:
        return []
    note_ids = [n.id for n, _ in rows]
    images: dict[int, list[str]] = {nid: [] for nid in note_ids}
    img_rows = (
        session.query(AnalysisImage)
        .filter(AnalysisImage.note_id.in_(note_ids))
        .order_by(AnalysisImage.id.asc())
        .all()
    )
    for img in img_rows:
        images[img.note_id].append(img.file_path)

    comment_counts: dict[int, int] = {nid: 0 for nid in note_ids}
    cc_rows = (
        session.query(NoteComment.note_id, func.count(NoteComment.id))
        .filter(NoteComment.note_id.in_(note_ids))
        .group_by(NoteComment.note_id)
        .all()
    )
    for nid, cnt in cc_rows:
        comment_counts[nid] = cnt

    return [
        AnalysisNoteDTO(
            id=n.id,
            pool_stock_id=n.pool_stock_id,
            user_id=n.user_id,
            username=u.username,
            content=n.content,
            created_at=n.created_at,
            image_paths=images.get(n.id, []),
            comment_count=comment_counts.get(n.id, 0),
        )
        for n, u in rows
    ]


# ============================================================
# 创建 / 编辑 / 删除
# ============================================================


def create_note(
    session: Session,
    pool_stock_id: int,
    user_id: int,
    content: str,
    uploaded_files: Iterable,
) -> AnalysisNote:
    """创建分析结论 + 保存图片。

    - 校验：pool_stock 存在
    - 校验：content 非空
    - 校验：每张图片 ≤ MAX_IMAGE_BYTES（由调用方在 UI 层先校验，这里再校验一次）
    - 流程：先创建 note → flush 拿 note_id → 保存图片 → 写入 AnalysisImage
    """
    pool_stock = session.get(PoolStock, pool_stock_id)
    if not pool_stock:
        raise ValueError("股票池中的股票不存在")

    content = (content or "").strip()
    if not content:
        raise ValueError("分析结论内容不能为空")

    files = list(uploaded_files)
    # 校验所有图片
    for f in files:
        ok, msg = validate_image_file(f)
        if not ok:
            raise ValueError(f"图片校验失败：{msg}")

    note = AnalysisNote(
        pool_stock_id=pool_stock_id,
        user_id=user_id,
        content=content,
    )
    session.add(note)
    session.flush()  # 拿到 note.id

    for f in files:
        rel_path = save_uploaded_image(f, user_id, note.id)
        img = AnalysisImage(note_id=note.id, file_path=rel_path)
        session.add(img)
    session.flush()

    from services.activity_service import record_activity
    record_activity(
        session, user_id, "write_note",
        f"对 {pool_stock.stock.code} {pool_stock.stock.name} 写了一条分析",
        pool_stock.pool_id,
    )

    return note


def update_note(
    session: Session,
    note_id: int,
    user_id: int,
    new_content: str,
    new_added_files: Iterable,
    removed_image_ids: Iterable[int],
) -> AnalysisNote:
    """编辑本人分析结论。

    - 校验：note.user_id == user_id（只能编辑自己的）
    - 校验：new_content 非空
    - 删除标记为移除的图片（DB 记录 + 本地文件）
    - 保存新增图片
    """
    note = session.get(AnalysisNote, note_id)
    if not note:
        raise ValueError("分析结论不存在")
    if note.user_id != user_id:
        raise ValueError("只能编辑自己的分析结论")

    new_content = (new_content or "").strip()
    if not new_content:
        raise ValueError("分析结论内容不能为空")

    # 删除标记为移除的图片
    removed_ids = list(removed_image_ids)
    if removed_ids:
        imgs_to_remove = (
            session.query(AnalysisImage)
            .filter(
                AnalysisImage.note_id == note_id,
                AnalysisImage.id.in_(removed_ids),
            )
            .all()
        )
        for img in imgs_to_remove:
            _delete_image_file(img.file_path)
            session.delete(img)
        session.flush()

    # 保存新增图片
    new_files = list(new_added_files)
    for f in new_files:
        ok, msg = validate_image_file(f)
        if not ok:
            raise ValueError(f"图片校验失败：{msg}")
    for f in new_files:
        rel_path = save_uploaded_image(f, user_id, note.id)
        img = AnalysisImage(note_id=note.id, file_path=rel_path)
        session.add(img)

    # 更新内容
    note.content = new_content
    session.flush()

    from services.activity_service import record_activity
    record_activity(
        session, user_id, "edit_note",
        f"编辑了 {note.pool_stock.stock.code} {note.pool_stock.stock.name} 的分析",
        note.pool_stock.pool_id,
    )

    return note


def delete_note(session: Session, note_id: int, user_id: int) -> None:
    """删除本人分析结论。

    - 校验：note.user_id == user_id
    - 删除关联图片文件（本地磁盘）
    - 删除 DB 记录（cascade 删除 AnalysisImage）
    """
    note = session.get(AnalysisNote, note_id)
    if not note:
        raise ValueError("分析结论不存在")
    if note.user_id != user_id:
        raise ValueError("只能删除自己的分析结论")

    # 先获取活动日志所需信息（删除后无法访问关系）
    pool_stock = note.pool_stock
    stock_code = pool_stock.stock.code
    stock_name = pool_stock.stock.name
    pool_id = pool_stock.pool_id

    # 删除关联的图片文件
    images = (
        session.query(AnalysisImage)
        .filter(AnalysisImage.note_id == note_id)
        .all()
    )
    for img in images:
        _delete_image_file(img.file_path)
    _delete_note_dir_if_empty(note.user_id, note.id)

    session.delete(note)
    session.flush()

    from services.activity_service import record_activity
    record_activity(
        session, user_id, "delete_note",
        f"删除了 {stock_code} {stock_name} 的分析",
        pool_id,
    )


def list_note_images(session: Session, note_id: int) -> list[AnalysisImage]:
    """列出某条 note 的图片（用于编辑页展示已有图片）。"""
    return (
        session.query(AnalysisImage)
        .filter(AnalysisImage.note_id == note_id)
        .order_by(AnalysisImage.id.asc())
        .all()
    )


# ============================================================
# 点评
# ============================================================


@dataclass
class CommentDTO:
    id: int
    note_id: int
    user_id: int
    username: str
    content: str
    created_at: datetime


def list_comments(session: Session, note_id: int) -> list[CommentDTO]:
    """列出某条笔记的点评（按时间正序）。"""
    rows = (
        session.query(NoteComment, User)
        .join(User, NoteComment.user_id == User.id)
        .filter(NoteComment.note_id == note_id)
        .order_by(NoteComment.created_at.asc())
        .all()
    )
    return [
        CommentDTO(
            id=c.id,
            note_id=c.note_id,
            user_id=c.user_id,
            username=u.username,
            content=c.content,
            created_at=c.created_at,
        )
        for c, u in rows
    ]


def add_comment(
    session: Session,
    note_id: int,
    user_id: int,
    content: str,
) -> NoteComment:
    """添加点评。"""
    content = (content or "").strip()
    if not content:
        raise ValueError("点评内容不能为空")

    note = session.get(AnalysisNote, note_id)
    if not note:
        raise ValueError("分析结论不存在")

    comment = NoteComment(note_id=note_id, user_id=user_id, content=content)
    session.add(comment)
    session.flush()

    from services.activity_service import record_activity
    record_activity(
        session, user_id, "comment",
        f"点评了 {note.pool_stock.stock.code} {note.pool_stock.stock.name} 的分析",
        note.pool_stock.pool_id,
    )

    return comment


def delete_comment(session: Session, comment_id: int, user_id: int) -> None:
    """删除本人点评。"""
    comment = session.get(NoteComment, comment_id)
    if not comment:
        raise ValueError("点评不存在")
    if comment.user_id != user_id:
        raise ValueError("只能删除自己的点评")
    session.delete(comment)
    session.flush()


# ============================================================
# 仪表盘 / 清理 辅助
# ============================================================


def delete_images_for_pool_stock(session: Session, pool_stock_id: int) -> int:
    """删除某 PoolStock 关联的所有磁盘图片文件。

    用于 delete_pool 同步清理磁盘文件。返回删除的文件数。
    不删除 DB 记录（由 cascade 处理）。
    """
    images = (
        session.query(AnalysisImage)
        .join(AnalysisNote, AnalysisImage.note_id == AnalysisNote.id)
        .filter(AnalysisNote.pool_stock_id == pool_stock_id)
        .all()
    )
    count = 0
    for img in images:
        _delete_image_file(img.file_path)
        count += 1
    return count
