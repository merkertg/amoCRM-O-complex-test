"""Настройка логирования без персональных данных и секретов.

- Код приложения не пишет в логи тексты сообщений, имена и контакты —
  только идентификаторы, длительности, коды ошибок и счётчики.
- RedactingFilter — страховка: маскирует токены, e-mail и телефоны,
  если они случайно окажутся в сообщении лога.
- В access-логе uvicorn убираются query string (там может быть секрет
  вебхука) и IP-адрес клиента.
"""

import logging
import re

_REDACTIONS = [
    (re.compile(r"(?i)(bearer\s+)[\w\-.~+/=]+"), r"\1***"),
    (re.compile(r"(?i)((?:token|secret|api[_-]?key|password)[\"']?\s*[:=]\s*[\"']?)[^\s\"'&,]+"), r"\1***"),
    (re.compile(r"\bsk-[\w\-]{8,}"), "sk-***"),
    (re.compile(r"\beyJ[\w\-]+\.[\w\-]+\.[\w\-]+"), "<jwt>"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "<email>"),
    (re.compile(r"(?<!\d)(?:\+7|8)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"), "<phone>"),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - некорректный формат лога не должен ронять приложение
            return True
        redacted = redact(message)
        if redacted != message:
            record.msg, record.args = redacted, None
        return True


class AccessLogFilter(logging.Filter):
    """uvicorn.access: args = (client_addr, method, full_path, http_version, status_code)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            _, method, path, version, status = record.args
            record.args = ("-", method, str(path).split("?", 1)[0], version, status)
        return True


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if not any(getattr(h, "_sales_assistant", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler.addFilter(RedactingFilter())
        handler._sales_assistant = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.setLevel(level.upper())
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, AccessLogFilter) for f in access.filters):
        access.addFilter(AccessLogFilter())
    # httpx пишет полные URL запросов на уровне INFO — нам это не нужно.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
