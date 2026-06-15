"""
用户服务 - 基于数据库的用户管理
"""

import hashlib
import importlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.database import get_postgres_db
from app.db.dual import dual_write_hot_document
from app.db.ids import DocumentId
from app.schemas.user import User, UserCreate, UserPreferences, UserResponse, UserUpdate

# 尝试导入日志管理器
try:
    from trader.utils.logging.manager import get_logger
except ImportError:
    # 如果导入失败，使用标准日志
    import logging

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)


logger = get_logger("user_service")


class UserService:
    """用户服务类"""

    def __init__(self):
        self.client = None

    async def _users_collection(self):
        return get_postgres_db().users

    def close(self, log: bool = True):
        """关闭数据库连接"""
        if log:
            logger.info("✅ UserService PostgreSQL 文档存储连接已释放")

    async def _dual_write_user(self, document: Dict[str, Any]) -> None:
        result = await dual_write_hot_document("users", document)
        if result.status == "failed":
            logger.warning("⚠️ 用户 PostgreSQL 双写失败: %s", result.reason)

    def __del__(self):
        """析构函数，确保连接被关闭"""
        try:
            self.close(log=False)
        except Exception:
            pass

    @staticmethod
    def hash_password(password: str) -> str:
        """密码哈希"""
        # 使用 bcrypt 会更安全，但为了兼容性先使用 SHA-256
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return UserService.hash_password(plain_password) == hashed_password

    async def create_user(self, user_data: UserCreate) -> Optional[User]:
        """创建用户"""
        try:
            users_collection = await self._users_collection()
            # 检查用户名是否已存在
            existing_user = await users_collection.find_one(
                {"username": user_data.username}
            )
            if existing_user:
                logger.warning(f"用户名已存在: {user_data.username}")
                return None

            # 检查邮箱是否已存在
            existing_email = await users_collection.find_one({"email": user_data.email})
            if existing_email:
                logger.warning(f"邮箱已存在: {user_data.email}")
                return None

            # 创建用户文档
            user_doc = {
                "username": user_data.username,
                "email": user_data.email,
                "hashed_password": self.hash_password(user_data.password),
                "is_active": True,
                "is_verified": False,
                "is_admin": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
                "preferences": {
                    # 分析偏好
                    "default_market": "A股",
                    "default_depth": "3",  # 1-5级，3级为标准分析（推荐）
                    "default_analysts": ["市场分析师", "基本面分析师"],
                    "auto_refresh": True,
                    "refresh_interval": 30,
                    # 外观设置
                    "ui_theme": "light",
                    "sidebar_width": 240,
                    # 语言和地区
                    "language": "zh-CN",
                    # 通知设置
                    "notifications_enabled": True,
                    "email_notifications": False,
                    "desktop_notifications": True,
                    "analysis_complete_notification": True,
                    "system_maintenance_notification": True,
                },
                "daily_quota": 1000,
                "concurrent_limit": 3,
                "total_analyses": 0,
                "successful_analyses": 0,
                "failed_analyses": 0,
                "favorite_stocks": [],
            }

            result = await users_collection.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id
            await self._dual_write_user(user_doc)

            logger.info(f"✅ 用户创建成功: {user_data.username}")
            return User(**user_doc)

        except Exception as e:
            logger.error(f"❌ 创建用户失败: {e}")
            return None

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """用户认证"""
        try:
            logger.info(f"🔍 [authenticate_user] 开始认证用户: {username}")

            # 查找用户
            user_doc = await self._get_user_document_by_username(username)
            logger.info(
                f"🔍 [authenticate_user] 数据库查询结果: {'找到用户' if user_doc else '用户不存在'}"
            )

            if not user_doc:
                logger.warning(f"❌ [authenticate_user] 用户不存在: {username}")
                return None

            logger.info(
                f"🔍 [authenticate_user] 用户信息: username={user_doc.get('username')}, email={user_doc.get('email')}, is_active={user_doc.get('is_active')}"
            )

            # 验证密码
            input_password_hash = self.hash_password(password)
            stored_password_hash = user_doc["hashed_password"]
            logger.info("🔍 [authenticate_user] 密码哈希对比:")
            logger.info(f"   输入密码哈希: {input_password_hash[:20]}...")
            logger.info(f"   存储密码哈希: {stored_password_hash[:20]}...")
            logger.info(f"   哈希匹配: {input_password_hash == stored_password_hash}")

            if not self.verify_password(password, user_doc["hashed_password"]):
                logger.warning(f"❌ [authenticate_user] 密码错误: {username}")
                return None

            # 检查用户是否激活
            if not user_doc.get("is_active", True):
                logger.warning(f"❌ [authenticate_user] 用户已禁用: {username}")
                return None

            # 更新最后登录时间
            users_collection = await self._users_collection()
            login_update = {"last_login": datetime.utcnow()}
            postgres_user_id = (
                DocumentId(user_doc["_id"])
                if isinstance(user_doc.get("_id"), str)
                and DocumentId.is_valid(user_doc["_id"])
                else user_doc["_id"]
            )
            await users_collection.update_one(
                {"_id": postgres_user_id}, {"$set": login_update}
            )
            await self._dual_write_user({**user_doc, **login_update})

            logger.info(f"✅ [authenticate_user] 用户认证成功: {username}")
            return User(**user_doc)

        except Exception as e:
            logger.error(f"❌ 用户认证失败: {e}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        try:
            user_doc = await self._get_user_document_by_username(username)
            return User(**user_doc) if user_doc else None
        except Exception as e:
            logger.error(f"❌ 获取用户失败: {e}")
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据用户ID获取用户"""
        try:
            if not DocumentId.is_valid(user_id):
                return None

            user_doc = await self._get_user_document_by_id(user_id)
            return User(**user_doc) if user_doc else None
        except Exception as e:
            logger.error(f"❌ 获取用户失败: {e}")
            return None

    async def update_user(self, username: str, user_data: UserUpdate) -> Optional[User]:
        """更新用户信息"""
        try:
            users_collection = await self._users_collection()
            update_data: Dict[str, Any] = {"updated_at": datetime.utcnow()}

            # 只更新提供的字段
            if user_data.email:
                # 检查邮箱是否已被其他用户使用
                existing_email = await users_collection.find_one(
                    {"email": user_data.email, "username": {"$ne": username}}
                )
                if existing_email:
                    logger.warning(f"邮箱已被使用: {user_data.email}")
                    return None
                update_data["email"] = user_data.email

            if user_data.preferences:
                update_data["preferences"] = user_data.preferences.model_dump()

            if user_data.daily_quota is not None:
                update_data["daily_quota"] = user_data.daily_quota

            if user_data.concurrent_limit is not None:
                update_data["concurrent_limit"] = user_data.concurrent_limit

            result = await users_collection.update_one(
                {"username": username}, {"$set": update_data}
            )

            if result.modified_count > 0:
                existing_user = await users_collection.find_one(
                    {"username": username}
                ) or {"username": username}
                await self._dual_write_user({**existing_user, **update_data})
                logger.info(f"✅ 用户信息更新成功: {username}")
                return await self.get_user_by_username(username)
            else:
                logger.warning(f"用户不存在或无需更新: {username}")
                return None

        except Exception as e:
            logger.error(f"❌ 更新用户信息失败: {e}")
            return None

    async def change_password(
        self, username: str, old_password: str, new_password: str
    ) -> bool:
        """修改密码"""
        try:
            # 验证旧密码
            user = await self.authenticate_user(username, old_password)
            if not user:
                logger.warning(f"旧密码验证失败: {username}")
                return False

            # 更新密码
            users_collection = await self._users_collection()
            new_hashed_password = self.hash_password(new_password)
            result = await users_collection.update_one(
                {"username": username},
                {
                    "$set": {
                        "hashed_password": new_hashed_password,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            if result.modified_count > 0:
                existing_user = await users_collection.find_one(
                    {"username": username}
                ) or {"username": username}
                await self._dual_write_user(
                    {
                        **existing_user,
                        "hashed_password": new_hashed_password,
                        "updated_at": datetime.utcnow(),
                    }
                )
                logger.info(f"✅ 密码修改成功: {username}")
                return True
            else:
                logger.error(f"❌ 密码修改失败: {username}")
                return False

        except Exception as e:
            logger.error(f"❌ 修改密码失败: {e}")
            return False

    async def reset_password(self, username: str, new_password: str) -> bool:
        """重置密码（管理员操作）"""
        try:
            users_collection = await self._users_collection()
            new_hashed_password = self.hash_password(new_password)
            result = await users_collection.update_one(
                {"username": username},
                {
                    "$set": {
                        "hashed_password": new_hashed_password,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            if result.modified_count > 0:
                existing_user = await users_collection.find_one(
                    {"username": username}
                ) or {"username": username}
                await self._dual_write_user(
                    {
                        **existing_user,
                        "hashed_password": new_hashed_password,
                        "updated_at": datetime.utcnow(),
                    }
                )
                logger.info(f"✅ 密码重置成功: {username}")
                return True
            else:
                logger.error(f"❌ 密码重置失败: {username}")
                return False

        except Exception as e:
            logger.error(f"❌ 重置密码失败: {e}")
            return False

    async def create_admin_user(
        self,
        username: str = "admin",
        password: str = "admin123",
        email: str = "admin@trader.cn",
    ) -> Optional[User]:
        """创建管理员用户"""
        try:
            users_collection = await self._users_collection()
            # 检查是否已存在管理员
            existing_admin = await users_collection.find_one({"username": username})
            if existing_admin:
                logger.info(f"管理员用户已存在: {username}")
                return User(**existing_admin)

            # 创建管理员用户文档
            admin_doc = {
                "username": username,
                "email": email,
                "hashed_password": self.hash_password(password),
                "is_active": True,
                "is_verified": True,
                "is_admin": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
                "preferences": {
                    "default_market": "A股",
                    "default_depth": "深度",
                    "ui_theme": "light",
                    "language": "zh-CN",
                    "notifications_enabled": True,
                    "email_notifications": False,
                },
                "daily_quota": 10000,  # 管理员更高配额
                "concurrent_limit": 10,
                "total_analyses": 0,
                "successful_analyses": 0,
                "failed_analyses": 0,
                "favorite_stocks": [],
            }

            result = await users_collection.insert_one(admin_doc)
            admin_doc["_id"] = result.inserted_id
            await self._dual_write_user(admin_doc)

            logger.info(f"✅ 管理员用户创建成功: {username}")
            logger.info(f"   密码: {password}")
            logger.info("   ⚠️  请立即修改默认密码！")

            return User(**admin_doc)

        except Exception as e:
            logger.error(f"❌ 创建管理员用户失败: {e}")
            return None

    async def set_admin(self, username: str, is_admin: bool) -> bool:
        """设置用户管理员状态。"""
        try:
            users_collection = await self._users_collection()
            update_data = {"is_admin": is_admin, "updated_at": datetime.utcnow()}
            result = await users_collection.update_one(
                {"username": username}, {"$set": update_data}
            )
            if result.modified_count <= 0:
                logger.warning("用户不存在或管理员状态无需更新: %s", username)
                return False

            existing_user = await users_collection.find_one(
                {"username": username}
            ) or {"username": username}
            await self._dual_write_user({**existing_user, **update_data})
            return True
        except Exception as e:
            logger.error("❌ 设置管理员状态失败: %s", e)
            return False

    async def list_users(self, skip: int = 0, limit: int = 100) -> List[UserResponse]:
        """获取用户列表"""
        try:
            if settings.POSTGRES_READ_ENABLED:
                postgres_users = await self._list_users_from_postgres(
                    skip=skip, limit=limit
                )
                if postgres_users:
                    return postgres_users

            users_collection = await self._users_collection()
            user_docs = await users_collection.find().skip(skip).limit(limit).to_list(
                None
            )
            users = []

            for user_doc in user_docs:
                user = User(**user_doc)
                users.append(
                    UserResponse(
                        id=str(user.id),
                        username=user.username,
                        email=user.email,
                        is_active=user.is_active,
                        is_verified=user.is_verified,
                        created_at=user.created_at,
                        last_login=user.last_login,
                        preferences=user.preferences,
                        daily_quota=user.daily_quota,
                        concurrent_limit=user.concurrent_limit,
                        total_analyses=user.total_analyses,
                        successful_analyses=user.successful_analyses,
                        failed_analyses=user.failed_analyses,
                    )
                )

            return users

        except Exception as e:
            logger.error(f"❌ 获取用户列表失败: {e}")
            return []

    async def _get_user_document_by_username(
        self, username: str
    ) -> Optional[Dict[str, Any]]:
        if settings.POSTGRES_READ_ENABLED:
            postgres_doc = await self._get_user_document_from_postgres(
                username=username
            )
            if postgres_doc:
                return postgres_doc
        users_collection = await self._users_collection()
        return await users_collection.find_one({"username": username})

    async def _get_user_document_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        if settings.POSTGRES_READ_ENABLED:
            postgres_doc = await self._get_user_document_from_postgres(user_id=user_id)
            if postgres_doc:
                return postgres_doc
        users_collection = await self._users_collection()
        return await users_collection.find_one({"_id": DocumentId(user_id)})

    async def _get_user_document_from_postgres(
        self,
        *,
        username: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            get_session_factory = getattr(
                importlib.import_module("app.core.session"), "get_session_factory"
            )
            get_user_by_legacy_id = getattr(
                importlib.import_module("app.db.account"), "get_user_by_legacy_id"
            )
            get_user_by_username = getattr(
                importlib.import_module("app.db.account"), "get_user_by_username"
            )

            async with get_session_factory()() as session:
                if username is not None:
                    document = await get_user_by_username(session, username)
                elif user_id is not None:
                    document = await get_user_by_legacy_id(session, user_id)
                else:
                    document = None

            if not document:
                return None
            return self._validated_postgres_user_document(document)
        except Exception as e:
            logger.warning(f"PostgreSQL用户查询失败，回退PostgreSQL: {e}")
            return None

    async def _list_users_from_postgres(
        self, *, skip: int, limit: int
    ) -> List[UserResponse]:
        try:
            get_session_factory = getattr(
                importlib.import_module("app.core.session"), "get_session_factory"
            )
            list_users = getattr(
                importlib.import_module("app.db.account"), "list_users"
            )

            async with get_session_factory()() as session:
                documents = await list_users(session, skip=skip, limit=limit)

            users = []
            for document in documents:
                response = self._postgres_user_response(document)
                if response:
                    users.append(response)
            return users
        except Exception as e:
            logger.warning(f"PostgreSQL用户列表查询失败，回退PostgreSQL: {e}")
            return []

    def _validated_postgres_user_document(
        self, document: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        user_id = str(document.get("_id") or "")
        if not DocumentId.is_valid(user_id):
            logger.warning(
                "PostgreSQL用户文档 legacy_id 不是有效 DocumentId，回退PostgreSQL: %s",
                user_id,
            )
            return None
        if not document.get("hashed_password"):
            logger.warning(
                "PostgreSQL用户文档缺少 hashed_password，回退PostgreSQL: %s",
                document.get("username"),
            )
            return None
        try:
            User(**document)
        except Exception as e:
            logger.warning(
                "PostgreSQL用户文档无法构造当前User模型，回退PostgreSQL: %s", e
            )
            return None
        return document

    def _postgres_user_response(
        self, document: Dict[str, Any]
    ) -> Optional[UserResponse]:
        user_id = str(document.get("_id") or "")
        if not DocumentId.is_valid(user_id):
            return None
        try:
            preferences = document.get("preferences") or {}
            return UserResponse(
                id=user_id,
                username=document["username"],
                email=document["email"],
                is_active=document.get("is_active", True),
                is_verified=document.get("is_verified", False),
                created_at=document.get("created_at") or datetime.utcnow(),
                last_login=document.get("last_login"),
                preferences=preferences
                if isinstance(preferences, UserPreferences)
                else UserPreferences(**preferences),
                daily_quota=document.get("daily_quota", 1000),
                concurrent_limit=document.get("concurrent_limit", 3),
                total_analyses=document.get("total_analyses", 0),
                successful_analyses=document.get("successful_analyses", 0),
                failed_analyses=document.get("failed_analyses", 0),
            )
        except Exception as e:
            logger.warning("PostgreSQL用户列表文档无法构造响应，跳过: %s", e)
            return None

    async def deactivate_user(self, username: str) -> bool:
        """禁用用户"""
        try:
            users_collection = await self._users_collection()
            result = await users_collection.update_one(
                {"username": username},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
            )

            if result.modified_count > 0:
                existing_user = await users_collection.find_one(
                    {"username": username}
                ) or {"username": username}
                await self._dual_write_user(
                    {
                        **existing_user,
                        "is_active": False,
                        "updated_at": datetime.utcnow(),
                    }
                )
                logger.info(f"✅ 用户已禁用: {username}")
                return True
            else:
                logger.warning(f"用户不存在: {username}")
                return False

        except Exception as e:
            logger.error(f"❌ 禁用用户失败: {e}")
            return False

    async def activate_user(self, username: str) -> bool:
        """激活用户"""
        try:
            users_collection = await self._users_collection()
            result = await users_collection.update_one(
                {"username": username},
                {"$set": {"is_active": True, "updated_at": datetime.utcnow()}},
            )

            if result.modified_count > 0:
                existing_user = await users_collection.find_one(
                    {"username": username}
                ) or {"username": username}
                await self._dual_write_user(
                    {
                        **existing_user,
                        "is_active": True,
                        "updated_at": datetime.utcnow(),
                    }
                )
                logger.info(f"✅ 用户已激活: {username}")
                return True
            else:
                logger.warning(f"用户不存在: {username}")
                return False

        except Exception as e:
            logger.error(f"❌ 激活用户失败: {e}")
            return False


# 全局用户服务实例
user_service = UserService()
