"""加密工具模块

提供 API Key 加密存储功能，使用 AES-256 加密算法。
"""

import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionError(Exception):
    """加密错误"""

    pass


class EncryptionManager:
    """加密管理器

    使用 AES-256 加密算法（通过 Fernet 实现）加密敏感数据。
    密钥通过主密码派生，支持密钥轮换。
    """

    DEFAULT_KEY_FILE = Path("data/.encryption_key")

    def __init__(self, master_key: str | None = None, key_file: str | Path | None = None):
        """初始化加密管理器

        Args:
            master_key: 主密码，如果为 None 则从环境变量或密钥文件读取
            key_file: 密钥文件路径
        """
        self._key_file = Path(key_file) if key_file else self.DEFAULT_KEY_FILE
        self._fernet: Fernet | None = None
        self._master_key = master_key

    def _get_master_key(self) -> str:
        """获取主密码"""
        if self._master_key:
            return self._master_key

        master_key = os.getenv("PUBLICHAGENT_MASTER_KEY")
        if master_key:
            return master_key

        if self._key_file and self._key_file.exists():
            return self._key_file.read_text(encoding="utf-8").strip()

        # 自动生成主密钥并保存
        master_key = self.generate_master_key()
        self._key_file.parent.mkdir(parents=True, exist_ok=True)
        self._key_file.write_text(master_key, encoding="utf-8")
        return master_key

    def _derive_key(self, salt: bytes) -> bytes:
        """从主密码派生加密密钥

        Args:
            salt: 盐值

        Returns:
            派生的密钥
        """
        master_key = self._get_master_key()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return key

    def _get_fernet(self, salt: bytes) -> Fernet:
        """获取 Fernet 实例

        Args:
            salt: 盐值

        Returns:
            Fernet 实例
        """
        key = self._derive_key(salt)
        return Fernet(key)

    def encrypt(self, plaintext: str, salt: bytes | None = None) -> str:
        """加密字符串

        Args:
            plaintext: 明文
            salt: 盐值，如果为 None 则生成随机盐值

        Returns:
            加密后的字符串（包含盐值）
        """
        if salt is None:
            salt = os.urandom(16)

        fernet = self._get_fernet(salt)
        encrypted = fernet.encrypt(plaintext.encode())

        return base64.urlsafe_b64encode(salt + encrypted).decode()

    def decrypt(self, encrypted_text: str) -> str:
        """解密字符串

        Args:
            encrypted_text: 加密的字符串（包含盐值）

        Returns:
            解密后的明文
        """
        try:
            data = base64.urlsafe_b64decode(encrypted_text.encode())
            salt = data[:16]
            encrypted = data[16:]

            fernet = self._get_fernet(salt)
            decrypted = fernet.decrypt(encrypted)

            return decrypted.decode()
        except Exception as e:
            raise EncryptionError(f"解密失败: {e}") from e

    @staticmethod
    def generate_master_key() -> str:
        """生成随机主密码

        Returns:
            随机生成的主密码
        """
        return base64.urlsafe_b64encode(os.urandom(32)).decode()


def encrypt_api_key(api_key: str, master_key: str | None = None) -> str:
    """加密 API Key

    Args:
        api_key: API Key
        master_key: 主密码

    Returns:
        加密后的 API Key
    """
    manager = EncryptionManager(master_key)
    return manager.encrypt(api_key)


def decrypt_api_key(encrypted_key: str, master_key: str | None = None) -> str:
    """解密 API Key

    Args:
        encrypted_key: 加密的 API Key
        master_key: 主密码

    Returns:
        解密后的 API Key
    """
    manager = EncryptionManager(master_key)
    return manager.decrypt(encrypted_key)
