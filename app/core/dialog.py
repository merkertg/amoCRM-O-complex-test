"""Разбор истории переписки, вставленной менеджером одним текстом.

Поддерживаемый формат — строки с префиксом роли:
    Клиент: Здравствуйте!
    Менеджер: Добрый день, чем помочь?
Строки без префикса считаются продолжением предыдущей реплики.
Текст до первого префикса сохраняется с ролью «unknown».
"""

import re

from app.schemas import DialogMessage, Role

_PREFIXES: dict[Role, tuple[str, ...]] = {
    Role.CLIENT: ("клиент", "покупатель", "client", "customer", "к"),
    Role.MANAGER: ("менеджер", "оператор", "продавец", "manager", "вы", "мы", "м"),
}
_LINE_RE = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?([A-Za-zА-Яа-яЁё]+)\s*[:：]\s*(.*)$")

ROLE_LABELS = {Role.CLIENT: "Клиент", Role.MANAGER: "Менеджер", Role.UNKNOWN: "Участник"}


def _role_for(prefix: str) -> Role | None:
    prefix = prefix.lower()
    for role, names in _PREFIXES.items():
        if prefix in names:
            return role
    return None


def parse_history_text(text: str) -> list[DialogMessage]:
    """Parse role-prefixed lines and append unprefixed lines to the last message."""
    messages: list[tuple[Role, list[str]]] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        match = _LINE_RE.match(line)
        role = _role_for(match.group(1)) if match else None
        if match is not None and role is not None:
            messages.append((role, [match.group(2).strip()]))
        elif line.strip():
            if messages:
                messages[-1][1].append(line.strip())
            else:
                messages.append((Role.UNKNOWN, [line.strip()]))
    result = []
    for role, parts in messages:
        body = "\n".join(p for p in parts if p).strip()
        if body:
            result.append(DialogMessage(role=role, text=body[:4000]))
    return result


def format_history(messages: list[DialogMessage]) -> str:
    return "\n".join(f"{ROLE_LABELS[m.role]}: {m.text}" for m in messages)
