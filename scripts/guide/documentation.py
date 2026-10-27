"""Append the shared Russian and English documentation navigation page."""

from reportlab.platypus import Spacer

from guide.i18n import tr
from guide.layout import (
    BLUE,
    BLUE_L,
    CELL,
    CELL_M,
    H2,
    SMALL,
    W,
    callout,
    p,
    simple_table,
)
from guide.toc import section


def add_documentation(story: list) -> None:
    """Explain repository documentation layers without introducing a new stage."""
    section(story, 30, tr(
        "Структура как в AI Support Agent: от кратких команд к подробным объяснениям и проверкам.",
        "The AI Support Agent structure: from short commands to detailed explanations and evidence.",
    ), BLUE)
    story += [
        simple_table([tr("Где читать", "Where to read"), tr("Для чего", "Purpose")], [
            ["README.md", tr("Описание, дорожная карта и общее оглавление.", "Overview, roadmap and complete documentation index.")],
            ["docs/instructions/", tr("Краткие инструкции: запуск, Windows, использование, проверки, интеграция, копии и приватность.", "Task instructions: setup, Windows, usage, checks, integration, backup and privacy.")],
            ["docs/STAGE_01.md … STAGE_08.md", tr("Подробные русские руководства восьми этапов и вопросы для самопроверки.", "Detailed Russian guides to eight stages and self-check questions.")],
            ["docs/DEMO.md", tr("Показ работы менеджера за 5–7 минут: заглушка, два блока, проверка и копирование.", "A 5–7 minute manager walkthrough: stub, two blocks, review and copying.")],
            ["docs/CI_CD.md", tr("Русский разбор CI и ручного запуска контейнера; фактические границы доставки.", "Russian walkthrough of CI and manual container operation; actual delivery scope.")],
            ["docs/RELEASES.md + RECOVERY.md", tr("Ручной выпуск и восстановление после сбоев.", "Manual release and recovery after failures.")],
            ["docs/DEPENDENCY_UPDATES.md", tr("Ручное обновление закреплённых зависимостей.", "Manual updates of pinned dependencies.")],
            ["docs/APPROACH.md + docs/adr/", tr("Подход и архитектурные решения на английском.", "Approach and architecture decisions in English.")],
            ["docs/VERIFICATION.md", tr("Текущие локальные проверки, ранее записанные результаты и ограничения.", "Current local checks, earlier recorded results and limitations.")],
            ["docs/DEVELOPMENT_LOG.md", tr("Какие шаги выполнены и что изменилось.", "Completed steps and what changed.")],
            ["docs/guide/", tr("Оба PDF, verification.json и инструкция пересборки.", "Both PDF editions, verification.json and rebuild instructions.")],
        ], [205, W - 205], [CELL_M, CELL]),
        Spacer(1, 10),
        p(tr("С чего начать", "Where to start"), H2),
        p(tr(
            "<b>Показ продукта:</b> DEMO → quickstart → usage.<br/>"
            "<b>Изучение:</b> STAGE_01 → следующие этапы → APPROACH.<br/>"
            "<b>Разработка:</b> testing → ci-and-delivery → CI_CD.<br/>"
            "<b>Проверенные результаты:</b> VERIFICATION → verification.json.",
            "<b>Product demonstration:</b> DEMO → quickstart → usage.<br/>"
            "<b>Learning:</b> STAGE_01 → subsequent stages → APPROACH.<br/>"
            "<b>Development:</b> testing → ci-and-delivery → CI_CD.<br/>"
            "<b>Verified results:</b> VERIFICATION → verification.json.",
        )),
        Spacer(1, 12),
        callout(tr(
            "Структура документации согласована с AI Support Agent. Нумерация этапов и описание "
            "возможностей относятся к этому проекту. Демонстрационная заглушка возвращает "
            "заранее заданный ответ и не измеряет качество настоящей LLM.",
            "Documentation organization follows AI Support Agent. Stage numbering and feature "
            "descriptions belong to this project. The demo stub returns a fixed answer "
            "and does not measure real LLM quality.",
        ), BLUE, BLUE_L),
        Spacer(1, 7),
        p(tr(
            "Полная карта файлов: docs/instructions/project-structure.md. Общая точка входа: README.md.",
            "Full file map: docs/instructions/project-structure.md. Main entry point: README.md.",
        ), SMALL),
    ]
