"""Оглавление PDF-гайда и заголовок раздела с новой страницы."""

from reportlab.platypus import PageBreak, Spacer

from guide.i18n import tr
from guide.layout import BLUE, SectionTitle

# Заголовки разделов (русский, английский). Номер раздела = позиция + 1.
CONTENTS = [
    ("Проект за минуту", "Project in a minute"),
    ("Путь запроса", "Request path"),
    ("Модули и зависимости", "Modules and dependencies"),
    ("Настройки и ошибки", "Settings and errors"),
    ("База знаний", "Knowledge base"),
    ("Проверка и перезагрузка", "Validation and reload"),
    ("Поиск: токены", "Retrieval: tokens"),
    ("Поиск: оценка", "Retrieval: scoring"),
    ("Промпт", "Prompt"),
    ("LLM-клиент", "LLM client"),
    ("Структурированный ответ", "Structured answer"),
    ("Пост-проверки", "Post-checks"),
    ("Injection и ПДн", "Injection and PII"),
    ("REST API", "REST API"),
    ("Интерфейс менеджера", "Manager UI"),
    ("Логи без ПДн", "Logs without PII"),
    ("Тесты", "Tests"),
    ("Docker", "Docker"),
    ("amoCRM: что даёт API", "amoCRM: what the API offers"),
    ("amoCRM: схема", "amoCRM: flow"),
    ("Вебхуки и кэш", "Webhooks and cache"),
    ("Токен виджета", "Widget token"),
    ("Виджет и адаптер", "Widget and adapter"),
    ("Шпаргалка команд", "Command cheat sheet"),
    ("Типичные ошибки", "Common errors"),
    ("Проверь себя", "Check yourself"),
    ("Итоги проверки", "Verification results"),
    ("CI и качество кода", "CI and code quality"),
    ("Оценка и защита доступа", "Evaluations and access"),
]

# Разделы каждого этапа ТЗ: на обложке оглавление окрашено по этапам.
STAGE_SECTIONS = {
    1: range(3, 5),
    2: range(5, 9),
    3: range(9, 14),
    4: range(14, 17),
    5: range(17, 19),
    6: range(19, 24),
    7: range(28, 29),
    8: range(29, 30),
}


def stage_of(number: int) -> int | None:
    """Номер этапа ТЗ, к которому относится раздел, или None для общих."""
    for stage, sections in STAGE_SECTIONS.items():
        if number in sections:
            return stage
    return None


def title(number: int) -> str:
    """Заголовок раздела на текущем языке."""
    ru, en = CONTENTS[number - 1]
    return tr(ru, en)


def section(story: list, number: int, subtitle: str, color=BLUE) -> None:
    """Начать раздел с новой страницы: номер, заголовок и подзаголовок."""
    if len(story) > 2:
        story.append(PageBreak())
    story.append(SectionTitle(str(number), title(number), subtitle, color))
    story.append(Spacer(1, 8))
