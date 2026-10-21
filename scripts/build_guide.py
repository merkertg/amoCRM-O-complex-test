"""Build the Russian and English learning guides from repository sources."""

import argparse
import json

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

from guide.diagrams import pipeline_flow, roadmap
from guide.documentation import add_documentation
from guide.evaluation import add_evaluation
from guide.i18n import LANGUAGES, set_language, tr
from guide.layout import (
    BLUE,
    BLUE_L,
    BODY,
    GREEN,
    GREEN_L,
    INK,
    LINE,
    MARGIN,
    MUTED,
    PAGE_H,
    PAGE_W,
    TEAL,
    TEAL_L,
    Diagram,
    SectionTitle,
    W,
    callout,
    cards,
    p,
    register_fonts,
    simple_table,
)
from guide.quality import add_quality
from guide.reference import add_reference
from guide.sources import PROJECT_ROOT, project_facts, test_counts
from guide.stages_core import add_stages_core
from guide.stages_delivery import add_stages_delivery
from guide.toc import CONTENTS, section, stage_of

OUTPUT = PROJECT_ROOT / "docs" / "guide"


class GuideDocument(SimpleDocTemplate):
    """Record section destinations for a clickable contents page and bookmarks."""

    def afterFlowable(self, flowable):
        """Attach navigation only after the heading reaches its final page."""
        if isinstance(flowable, SectionTitle):
            key = f"section-{flowable.number}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(
                f"{flowable.number}. {flowable.title}", key, level=0,
            )


def page_frame(canvas, document):
    """Draw the same restrained header and page number on every page."""
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN, PAGE_H - 34, PAGE_W - MARGIN, PAGE_H - 34)
    canvas.setFont("PT", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, PAGE_H - 25, "AI Sales Assistant | amoCRM")
    canvas.drawRightString(
        PAGE_W - MARGIN, PAGE_H - 25,
        tr("Учебное руководство · RU", "Learning guide · EN"),
    )
    canvas.drawString(MARGIN, 26, tr("Демонстрационные данные · КлиматДом", "Fictional demo data · KlimatDom"))
    canvas.drawRightString(PAGE_W - MARGIN, 26, str(document.page))
    canvas.restoreState()


def add_introduction(story, facts, verification):
    """Explain the product, navigation and human review before the stage guides."""
    cover = ParagraphStyle("cover", parent=BODY, fontName="PT-Bold", fontSize=32, leading=38, textColor=INK)
    lead = ParagraphStyle("lead", parent=BODY, fontSize=14, leading=21)
    story += [
        Spacer(1, 25),
        p("AI Sales Assistant<br/>" + tr("для amoCRM", "for amoCRM"), cover),
        Spacer(1, 18),
        p(tr("От сообщения клиента до двух блоков ответа", "From a customer message to two answer blocks"), lead),
        Spacer(1, 16),
        p(tr(
            "Практическое руководство по этапам 01–08: архитектура, база знаний, поиск, LLM, "
            "защитные проверки, интерфейс, тесты, Docker, интеграция с CRM, CI, оценки и защита доступа.",
            "A practical guide to stages 01–08: architecture, knowledge base, retrieval, LLM, "
            "guards, UI, tests, Docker, CRM integration, CI, evaluations and access protection.",
        )),
        Spacer(1, 20),
        Diagram(64, roadmap),
        Spacer(1, 18),
        cards([
            (str(facts["products"]), tr("товаров и услуг в базе знаний", "products and services in the knowledge base"), TEAL, TEAL_L),
            (str(facts["faq"]), tr("ответов на общие вопросы", "general FAQ entries"), BLUE, BLUE_L),
            (str(verification["tests"]["passed"]), tr("пройденных тестов сервиса", "passing service tests"), GREEN, GREEN_L),
        ]),
        Spacer(1, 14),
        callout(tr(
            "<b>Решение принимает менеджер.</b> Ассистент готовит ответ и внутреннюю подсказку. "
            "Менеджер проверяет факты, редактирует и сам отправляет сообщение клиенту.",
            "<b>The manager decides.</b> The assistant prepares a reply and an internal hint. "
            "The manager checks facts, edits and sends the customer message.",
        )),
        Spacer(1, 12),
        p(tr(
            "Код и примеры извлекаются из файлов проекта при сборке. Результаты прошлых "
            "проверок берутся из verification.json; сборка PDF сама не проверяет настоящий "
            "аккаунт amoCRM, качество LLM или Docker.",
            "Code and examples are extracted from repository files at build time. Prior check "
            "results come from verification.json; building a PDF does not verify a real amoCRM "
            "account, LLM quality or Docker.",
        )),
        PageBreak(),
        p(tr("Оглавление", "Contents"), cover),
        Spacer(1, 12),
    ]
    rows = []
    for number, pair in enumerate(CONTENTS, start=1):
        stage = stage_of(number)
        rows.append([
            str(number),
            f'<link href="#section-{number}" color="#2563EB">{tr(*pair)}</link>',
            f"{stage:02}" if stage else "—",
        ])
    story += [
        simple_table(["#", tr("Раздел — нажмите для перехода", "Section — click to open"), tr("Этап", "Stage")], rows, [30, W - 85, 55]),
    ]
    section(story, 1, tr("Задача продукта и границы MVP.", "Product goal and MVP boundaries."))
    story += [
        p(tr(
            "Менеджер получает вопрос клиента и историю диалога. Сервис ищет факты в "
            "data/knowledge_base.json и просит модель вернуть структурированный ответ. "
            "КлиматДом, товары, цены и переписка в примерах вымышлены.",
            "The manager receives a customer question and conversation history. The service "
            "retrieves facts from data/knowledge_base.json and asks the model for a structured "
            "answer. KlimatDom, its products, prices and sample conversations are fictional.",
        )),
        Spacer(1, 12),
        cards([
            (tr("Ответ клиенту", "Customer reply"), tr("Вежливый ответ по найденным фактам; уточняющий вопрос, если информации мало.", "A polite reply grounded in retrieved facts; a clarifying question if information is missing."), BLUE, BLUE_L),
            (tr("Подсказка менеджеру", "Manager hint"), tr("Уместность допродажи, позиция из базы знаний, причина и пример фразы.", "Upsell appropriateness, a knowledge-base item, reason and sample phrase."), TEAL, TEAL_L),
        ], columns=2),
        Spacer(1, 12),
        simple_table([tr("Граница", "Boundary"), tr("Что это означает", "Meaning")], [
            [tr("Факты", "Facts"), tr("Только база знаний компании. Проверки предупреждают об ошибках, но не доказывают истинность каждого предложения модели.", "Only the company knowledge base. Guards warn about errors but do not prove every model sentence true.")],
            [tr("Отправка", "Sending"), tr("Кнопки копируют текст. В проекте нет автоматической отправки в чат клиента.", "Buttons copy text. The project has no automatic customer-chat sending.")],
            [tr("Проверка", "Verification"), tr("Тесты используют FakeLLM и MockTransport. Настоящие LLM и аккаунт amoCRM требуют отдельной проверки.", "Tests use FakeLLM and MockTransport. A real LLM and amoCRM account require separate verification.")],
        ], [105, W - 105]),
    ]
    section(story, 2, tr("Один pipeline для ручного ввода и виджета amoCRM.", "One pipeline for manual input and the amoCRM widget."))
    story += [
        Diagram(158, pipeline_flow), Spacer(1, 16),
        simple_table([tr("Шаг", "Step"), tr("Что происходит", "What happens")], [
            ["1. DialogContext", tr("Текущий вопрос, история, имя и источник запроса.", "Current question, history, name and request source.")],
            ["2. KnowledgeIndex", tr("Поиск по ключевым словам и добавление связанных позиций.", "Keyword retrieval and related items.")],
            ["3. LLMClient", tr("Промпт с фактами и отдельными блоками недоверенных данных.", "A prompt with facts and separate blocks of untrusted data.")],
            ["4. Suggestion", tr("JSON проходит проверку схемы и защитные проверки. Если структура сломана — одна попытка починки.", "JSON goes through schema validation and guards. Invalid structure gets one repair attempt.")],
            ["5. SuggestResponse", tr("Два блока, источники и предупреждения для менеджера.", "Two blocks, sources and warnings for the manager.")],
        ], [120, W - 120]),
        Spacer(1, 14),
        callout(tr(
            "Просматривайте примеры вместе с исходниками. Фрагменты кода и длинные строки "
            "в этом PDF могут переноситься для чтения; команды копируйте из Markdown-инструкций.",
            "Read examples alongside the source files. Code excerpts and long lines in this "
            "PDF may wrap for readability; copy commands from the Markdown instructions.",
        )),
    ]


def build(language, facts, counts, verification):
    """Build one language with embedded fonts and stable repository output names."""
    set_language(language)
    story = []
    add_introduction(story, facts, verification)
    add_stages_core(story, facts)
    add_stages_delivery(story, facts, counts)
    add_reference(story, verification)
    add_quality(story, verification)
    add_evaluation(story, verification)
    add_documentation(story)
    suffix = "-en" if language == "en" else ""
    destination = OUTPUT / f"amocrm-sales-assistant-guide{suffix}.pdf"
    document = GuideDocument(
        str(destination), pagesize=(PAGE_W, PAGE_H),
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=48, bottomMargin=45,
        title=tr("AI Sales Assistant для amoCRM — учебное руководство", "AI Sales Assistant for amoCRM — learning guide"),
        author="AI Forge", pageCompression=1,
    )
    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return destination


def main():
    """Read safe project facts once; generate both languages unless selected."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=(*LANGUAGES, "all"), default="all")
    args = parser.parse_args()
    verification = json.loads((OUTPUT / "verification.json").read_text(encoding="utf-8"))
    register_fonts()
    facts, counts = project_facts(), test_counts()
    if sum(counts.values()) != verification["tests"]["total"]:
        parser.error("Collected test count differs from verification.json; rerun tests and update the evidence.")
    for language in LANGUAGES if args.lang == "all" else (args.lang,):
        destination = build(language, facts, counts, verification)
        print(f"Built {language}: {destination.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
