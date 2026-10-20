"""Базовый класс ошибок приложения.

Каждая ошибка знает свой HTTP-статус, машинный код и понятное менеджеру
сообщение. API превращает их в ответ вида {"error": {"code", "message"}}.
"""


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    user_message: str = "Внутренняя ошибка сервиса. Попробуйте ещё раз."

    def __init__(self, user_message: str | None = None) -> None:
        if user_message:
            self.user_message = user_message
        super().__init__(self.user_message)
