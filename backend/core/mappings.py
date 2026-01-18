ROLE_LABELS = {
    "ADMIN": "Администратор",
    "OPERATOR": "Оператор",
}

ACTION_LABELS = {
    "login": "Вход в систему",
    "logout": "Выход из системы",
}

ROLE_LABELS_REVERSE = {v.lower(): k for k, v in ROLE_LABELS.items()}

ACTION_LABELS_REVERSE = {v.lower(): k for k, v in ACTION_LABELS.items()}
