from enum import Enum

class AuditAction(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
