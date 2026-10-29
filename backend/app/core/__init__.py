# Core module exports
from app.core.config import settings
from app.core.database import get_db, init_db, close_db, async_session_factory
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.core.deps import (
    get_current_user,
    get_current_active_user,
    RoleChecker,
    require_admin,
    require_instructor,
    require_student,
    require_admin_or_instructor,
)

__all__ = [
    "settings",
    "get_db",
    "init_db",
    "close_db",
    "async_session_factory",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "get_current_active_user",
    "RoleChecker",
    "require_admin",
    "require_instructor",
    "require_student",
    "require_admin_or_instructor",
]
