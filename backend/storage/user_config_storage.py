"""用户配置存储管理器

提供用户配置的持久化存储，使用 SQLite 数据库。
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.models.user_config import (
    CustomModelConfig,
    UserAPIKeys,
    UserConfig,
    UserPreferences,
)
from backend.utils.encryption import EncryptionError, EncryptionManager


class UserConfigStorage:
    """用户配置存储管理器

    使用 SQLite 存储用户配置，API Key 使用 AES-256 加密。
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        encryption_manager: EncryptionManager | None = None,
    ):
        """初始化存储管理器

        Args:
            db_path: 数据库文件路径
            encryption_manager: 加密管理器
        """
        self._db_path = Path(db_path) if db_path else Path("data/user_configs.db")
        self._encryption_manager = encryption_manager or EncryptionManager()
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_configs (
                    user_id TEXT PRIMARY KEY,
                    api_keys TEXT NOT NULL DEFAULT '{}',
                    custom_models TEXT NOT NULL DEFAULT '{}',
                    enabled_skills TEXT NOT NULL DEFAULT '[]',
                    preferences TEXT NOT NULL DEFAULT '{}',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

            cursor = conn.execute("PRAGMA table_info(user_configs)")
            columns = {row[1] for row in cursor.fetchall()}

            if "custom_models" not in columns:
                conn.execute("ALTER TABLE user_configs ADD COLUMN custom_models TEXT NOT NULL DEFAULT '{}'")
                conn.commit()
            if "enabled_skills" not in columns:
                conn.execute("ALTER TABLE user_configs ADD COLUMN enabled_skills TEXT NOT NULL DEFAULT '[]'")
                conn.commit()
            if "preferences" not in columns:
                conn.execute("ALTER TABLE user_configs ADD COLUMN preferences TEXT NOT NULL DEFAULT '{}'")
                conn.commit()
            if "metadata" not in columns:
                conn.execute("ALTER TABLE user_configs ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
                conn.commit()

    def _encrypt_api_keys(self, api_keys: UserAPIKeys) -> dict[str, str]:
        """加密 API Keys

        Args:
            api_keys: API Keys（明文）

        Returns:
            加密后的 API Keys 字典
        """
        encrypted = {}
        for provider, key in api_keys.model_dump().items():
            if key:
                try:
                    encrypted[provider] = self._encryption_manager.encrypt(key)
                except EncryptionError:
                    encrypted[provider] = ""
            else:
                encrypted[provider] = ""
        return encrypted

    def _decrypt_api_keys(self, encrypted_keys: dict[str, str]) -> UserAPIKeys:
        """解密 API Keys

        Args:
            encrypted_keys: 加密的 API Keys 字典

        Returns:
            解密后的 API Keys
        """
        decrypted: dict[str, str | None] = {}
        for provider, encrypted_key in encrypted_keys.items():
            if encrypted_key:
                try:
                    decrypted[provider] = self._encryption_manager.decrypt(encrypted_key)
                except EncryptionError:
                    decrypted[provider] = None
            else:
                decrypted[provider] = None
        return UserAPIKeys(**decrypted)

    def _encrypt_custom_models(self, custom_models: dict[str, CustomModelConfig]) -> dict[str, dict]:
        """加密自定义模型配置中的 API Key

        Args:
            custom_models: 自定义模型配置

        Returns:
            加密后的配置字典
        """
        encrypted = {}
        for model_name, config in custom_models.items():
            config_dict = config.model_dump()
            if config_dict.get("api_key"):
                try:
                    config_dict["api_key"] = self._encryption_manager.encrypt(config_dict["api_key"])
                except EncryptionError:
                    config_dict["api_key"] = ""
            encrypted[model_name] = config_dict
        return encrypted

    def _decrypt_custom_models(self, encrypted_models: dict[str, dict]) -> dict[str, CustomModelConfig]:
        """解密自定义模型配置中的 API Key

        Args:
            encrypted_models: 加密的模型配置

        Returns:
            解密后的模型配置
        """
        decrypted = {}
        for model_name, config_dict in encrypted_models.items():
            if config_dict.get("api_key"):
                try:
                    config_dict["api_key"] = self._encryption_manager.decrypt(config_dict["api_key"])
                except EncryptionError:
                    config_dict["api_key"] = None
            decrypted[model_name] = CustomModelConfig(**config_dict)
        return decrypted

    def get(self, user_id: str) -> UserConfig | None:
        """获取用户配置

        Args:
            user_id: 用户 ID

        Returns:
            用户配置，如果不存在则返回 None
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM user_configs WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            api_keys = self._decrypt_api_keys(json.loads(row["api_keys"]))
            custom_models = self._decrypt_custom_models(json.loads(row["custom_models"]))
            enabled_skills = json.loads(row["enabled_skills"])
            preferences = UserPreferences(**json.loads(row["preferences"]))
            metadata = json.loads(row["metadata"])

            return UserConfig(
                user_id=row["user_id"],
                api_keys=api_keys,
                custom_models=custom_models,
                enabled_skills=enabled_skills,
                preferences=preferences,
                metadata=metadata,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    def save(self, config: UserConfig) -> None:
        """保存用户配置

        Args:
            config: 用户配置
        """
        encrypted_keys = self._encrypt_api_keys(config.api_keys)
        encrypted_models = self._encrypt_custom_models(config.custom_models)

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_configs
                (user_id, api_keys, custom_models, enabled_skills, preferences, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    config.user_id,
                    json.dumps(encrypted_keys),
                    json.dumps(encrypted_models),
                    json.dumps(config.enabled_skills),
                    json.dumps(config.preferences.model_dump()),
                    json.dumps(config.metadata),
                    config.created_at.isoformat(),
                    config.updated_at.isoformat(),
                ),
            )
            conn.commit()

    def update(self, user_id: str, updates: dict[str, Any]) -> UserConfig | None:
        """更新用户配置

        Args:
            user_id: 用户 ID
            updates: 更新内容

        Returns:
            更新后的配置，如果用户不存在则返回 None
        """
        config = self.get(user_id)
        if config is None:
            return None

        if "api_keys" in updates:
            config.api_keys = UserAPIKeys(**updates["api_keys"])
        if "custom_models" in updates:
            config.custom_models = {
                k: CustomModelConfig(**v) for k, v in updates["custom_models"].items()
            }
        if "enabled_skills" in updates:
            config.enabled_skills = updates["enabled_skills"]
        if "preferences" in updates:
            config.preferences = UserPreferences(**updates["preferences"])
        if "metadata" in updates:
            config.metadata = updates["metadata"]

        config.touch()
        self.save(config)
        return config

    def delete(self, user_id: str) -> bool:
        """删除用户配置

        Args:
            user_id: 用户 ID

        Returns:
            是否删除成功
        """
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM user_configs WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_users(self) -> list[str]:
        """列出所有用户 ID

        Returns:
            用户 ID 列表
        """
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("SELECT user_id FROM user_configs")
            return [row[0] for row in cursor.fetchall()]

    def set_api_key(self, user_id: str, provider: str, api_key: str) -> None:
        """设置用户的 API Key

        Args:
            user_id: 用户 ID
            provider: 提供商名称
            api_key: API Key（明文）
        """
        config = self.get(user_id)
        if config is None:
            config = UserConfig(user_id=user_id)

        api_keys_dict = config.api_keys.model_dump()
        api_keys_dict[provider] = api_key
        config.api_keys = UserAPIKeys(**api_keys_dict)
        config.touch()

        self.save(config)

    def get_api_key(self, user_id: str, provider: str) -> str | None:
        """获取用户的 API Key

        Args:
            user_id: 用户 ID
            provider: 提供商名称

        Returns:
            API Key（明文），如果不存在则返回 None
        """
        config = self.get(user_id)
        if config is None:
            return None

        return getattr(config.api_keys, provider, None)

    def add_custom_model(
        self,
        user_id: str,
        model_name: str,
        config: CustomModelConfig,
    ) -> None:
        """添加自定义模型

        Args:
            user_id: 用户 ID
            model_name: 模型唯一标识名称
            config: 模型配置
        """
        user_config = self.get(user_id)
        if user_config is None:
            user_config = UserConfig(user_id=user_id)

        user_config.custom_models[model_name] = config
        user_config.touch()
        self.save(user_config)

    def update_custom_model(
        self,
        user_id: str,
        model_name: str,
        updates: dict[str, Any],
    ) -> CustomModelConfig | None:
        """更新自定义模型

        Args:
            user_id: 用户 ID
            model_name: 模型名称
            updates: 更新内容

        Returns:
            更新后的配置，如果模型不存在则返回 None
        """
        user_config = self.get(user_id)
        if user_config is None or model_name not in user_config.custom_models:
            return None

        current_config = user_config.custom_models[model_name]
        config_dict = current_config.model_dump()
        config_dict.update({k: v for k, v in updates.items() if v is not None})

        updated_config = CustomModelConfig(**config_dict)
        user_config.custom_models[model_name] = updated_config
        user_config.touch()
        self.save(user_config)

        return updated_config

    def delete_custom_model(self, user_id: str, model_name: str) -> bool:
        """删除自定义模型

        Args:
            user_id: 用户 ID
            model_name: 模型名称

        Returns:
            是否删除成功
        """
        user_config = self.get(user_id)
        if user_config is None or model_name not in user_config.custom_models:
            return False

        del user_config.custom_models[model_name]
        user_config.touch()
        self.save(user_config)
        return True

    def get_custom_model(self, user_id: str, model_name: str) -> CustomModelConfig | None:
        """获取自定义模型配置

        Args:
            user_id: 用户 ID
            model_name: 模型名称

        Returns:
            模型配置，如果不存在则返回 None
        """
        user_config = self.get(user_id)
        if user_config is None:
            return None

        return user_config.custom_models.get(model_name)

    def list_custom_models(self, user_id: str) -> dict[str, CustomModelConfig]:
        """列出用户的所有自定义模型

        Args:
            user_id: 用户 ID

        Returns:
            模型配置字典
        """
        user_config = self.get(user_id)
        if user_config is None:
            return {}

        return user_config.custom_models

    def set_model_selection(
        self,
        user_id: str,
        model_type: str,
        model_name: str,
    ) -> None:
        """设置模型选择

        Args:
            user_id: 用户 ID
            model_type: 模型类型 (planner/executor)
            model_name: 模型名称
        """
        user_config = self.get(user_id)
        if user_config is None:
            user_config = UserConfig(user_id=user_id)

        if model_type == "planner":
            user_config.preferences.planner_model = model_name
        elif model_type == "executor":
            user_config.preferences.executor_model = model_name

        user_config.touch()
        self.save(user_config)


_storage: UserConfigStorage | None = None


def get_user_config_storage() -> UserConfigStorage:
    """获取全局用户配置存储实例

    Returns:
        UserConfigStorage 实例
    """
    global _storage
    if _storage is None:
        _storage = UserConfigStorage()
    return _storage


def reset_user_config_storage() -> None:
    """重置全局用户配置存储实例"""
    global _storage
    _storage = None
