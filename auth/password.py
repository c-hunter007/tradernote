"""密码哈希工具（bcrypt）。"""
import bcrypt


def hash_password(plain: str) -> str:
    """对明文密码进行 bcrypt 哈希。返回 utf-8 字符串。"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
