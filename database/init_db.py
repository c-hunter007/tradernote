"""数据库初始化：建表 + 迁移。"""
from sqlalchemy import text

from database.db import engine
from database.models import Base


def init_db() -> None:
    """根据模型创建所有表 + 执行增量迁移。"""
    Base.metadata.create_all(engine)

    # 迁移：stock_pools 新增 feishu_webhook 列
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE stock_pools ADD COLUMN feishu_webhook VARCHAR(512)"
            ))
            conn.commit()
    except Exception:
        pass  # 列已存在时忽略

    # 迁移：operation_plans 新增完成记录列
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE operation_plans ADD COLUMN completion_note TEXT"
            ))
            conn.commit()
    except Exception:
        pass  # 列已存在时忽略
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE operation_plans ADD COLUMN completed_at DATETIME"
            ))
            conn.commit()
    except Exception:
        pass  # 列已存在时忽略


if __name__ == "__main__":
    init_db()
    print("数据库初始化完成。")
