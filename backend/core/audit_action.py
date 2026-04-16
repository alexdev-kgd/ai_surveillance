from enum import Enum

class AuditAction(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    AI_SETTINGS_UPDATE = "aiSettingsUpdate"
    AI_SETTINGS_ACCESS = "aiSettingsAccess"
    PERMISSION_SETTINGS_UPDATE = "permissionSettingsUpdate"
    PERMISSION_SETTINGS_ACCESS = "permissionSettingsAccess"
    AUDIT_ACCESS = "auditAccess"
    VIDEO_ANALYSIS = "videoAnalysis"
    CAMERA_SETTINGS_ACCESS = "cameraSettingsAccess"
    CAMERA_ADDED = "cameraAdded"
    CAMERA_DELETED = "cameraDeleted"
    CAMERA_ENABLED = "cameraEnabled"
    CAMERA_DISABLED = "cameraDisabled"
