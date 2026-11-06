"""密码哈希与校验。"""

import bcrypt

BCRYPT_MAX_PASSWORD_BYTES = 72
BCRYPT_ROUNDS = 12


def _encode_password(password: str) -> bytes:
    """将密码编码为 UTF-8 并检查 bcrypt 长度限制。"""
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("密码 UTF-8 编码后不能超过 72 字节")
    return encoded


def hash_password(password: str) -> str:
    """使用 bcrypt 生成密码哈希。"""
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    password_hash = bcrypt.hashpw(_encode_password(password), salt)
    return password_hash.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    try:
        return bcrypt.checkpw(
            _encode_password(password),
            password_hash.encode("utf-8"),
        )
    except (TypeError, ValueError):
        return False
