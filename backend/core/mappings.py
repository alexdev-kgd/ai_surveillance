ROLE_LABELS = {
    "ADMIN": "Администратор",
    "OPERATOR": "Оператор",
}

ACTION_LABELS = {
    "login": "Вход в систему",
    "logout": "Выход из системы",
    "aiSettingsUpdate": "Изменение настроек ИИ модели",
    "aiSettingsAccess": "Просмотр настроек ИИ модели",
    "permissionSettingsUpdate": "Изменение настроек разрешений пользователей",
    "permissionSettingsAccess": "Просмотр настроек разрешений пользователей",
    "auditAccess": "Просмотр аудита",
    "videoAnalysis": "Анализ видео",
}

ROLE_LABELS_REVERSE = {v.lower(): k for k, v in ROLE_LABELS.items()}

ACTION_LABELS_REVERSE = {v.lower(): k for k, v in ACTION_LABELS.items()}
