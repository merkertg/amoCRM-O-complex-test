"""Схемы PDF-гайда. Каждая функция рисует одну схему на холсте ReportLab.

Подписи задаются парами tr(русский, английский); язык выбирается до сборки.
Схемы, которым нужны данные проекта (оценки поиска), получают их аргументом
через functools.partial.
"""

from reportlab.pdfbase import pdfmetrics

from guide.i18n import tr
from guide.layout import (
    AMBER,
    AMBER_L,
    BLUE,
    BLUE_L,
    GREEN,
    GREEN_L,
    INK,
    LINE,
    MUTED,
    ORANGE,
    ORANGE_L,
    SLATE_L,
    SOFT,
    TEAL,
    TEAL_L,
    TEXT,
    VIOLET,
    VIOLET_L,
    WHITE,
    arrow,
    chip,
    circle_num,
    draw_text,
    lines_in,
    node,
    poly_arrow,
    rbox,
)

# Все шесть этапов ТЗ и этапы 07 (CI) и 08 (оценка и доступ) выполнены.
STAGES_DONE = 8


def roadmap(c, w, h):
    """Шесть этапов ТЗ и этапы 07–08: все выполнены."""
    titles = [
        tr("Архитектура и структура", "Architecture and layout"),
        tr("База знаний и поиск", "Knowledge base and retrieval"),
        tr("LLM и два блока ответа", "LLM and two answer blocks"),
        tr("FastAPI и интерфейс", "FastAPI and UI"),
        tr("Тесты и Docker", "Tests and Docker"),
        tr("Интеграция с amoCRM", "amoCRM integration"),
        tr("CI и качество кода", "CI and code quality"),
        tr("Оценка и доступ", "Evaluations and access"),
    ]
    gap, bh = 6, 58
    bw = (w - (len(titles) - 1) * gap) / len(titles)
    y = h - bh
    for index, title in enumerate(titles):
        x = index * (bw + gap)
        rbox(c, x, y, bw, bh, GREEN_L, GREEN, r=7, lw=1)
        circle_num(c, x + 10, y + bh - 10, 6.5, str(index + 1), GREEN, WHITE, 7.5)
        status = tr("готово", "done")
        width = pdfmetrics.stringWidth(status, "PT-Bold", 6) + 6
        chip(c, x + bw - width - 3, y + bh - 16, status, GREEN, WHITE, "PT-Bold", 6, pad=3, h=11)
        lines_in(c, x + bw / 2, y + bh - 23, bw - 6, title, "PT-Bold", 7.4, 9, INK)


def pipeline_flow(c, w, h):
    """Шесть шагов pipeline от DialogContext до SuggestResponse."""
    steps = [
        (tr("Нормализация", "Normalise"), tr("очистка, лимиты,\nПДн, injection", "sanitise, limits,\nPII, injection"), ORANGE_L, ORANGE),
        (tr("Поиск", "Retrieve"), tr("до 5 позиций\n+ 3 связанные", "up to 5 items\n+ 3 related"), TEAL_L, TEAL),
        (tr("Промпт", "Prompt"), tr("правила + блоки\nданных", "rules + data\nblocks"), BLUE_L, BLUE),
        ("LLM", tr("повторы при\nсбоях", "retries on\nfailures"), VIOLET_L, VIOLET),
        (tr("Валидация", "Validate"), tr("JSON → Suggestion,\n1 починка", "JSON → Suggestion,\n1 repair"), AMBER_L, AMBER),
        (tr("Пост-проверки", "Post-checks"), tr("допродажа, утечки,\nсуммы", "upsell, leaks,\namounts"), GREEN_L, GREEN),
    ]
    # Блоки выше текста: номер в углу не должен закрывать заголовок шага.
    gap, bh = 10, 78
    bw = (w - 5 * gap) / 6
    y = h - 34 - bh
    node(c, 0, h - 26, 120, 22, "DialogContext", "", SOFT, LINE, 9)
    node(c, w - 130, 2, 130, 22, "SuggestResponse", "", SOFT, LINE, 9)
    arrow(c, 60, h - 27, 60, y + bh + 2)
    for index, (title, sub, fill, edge) in enumerate(steps):
        x = index * (bw + gap)
        node(c, x, y, bw, bh, title, sub, fill, edge, 9.5, 7.6)
        circle_num(c, x + 9, y + bh - 9, 6.5, str(index + 1), edge, WHITE, 7.5)
        if index < len(steps) - 1:
            arrow(c, x + bw + 1, y + bh / 2, x + bw + gap - 1, y + bh / 2)
    last_x = 5 * (bw + gap) + bw / 2
    poly_arrow(c, [(last_x, y - 1), (last_x, 26)])


def module_map(c, w, h):
    """Модули и направление зависимостей."""
    bw, bh = 128, 50
    api = (0, h / 2 - bh / 2)
    core = (w / 2 - bw / 2, h - bh - 6)
    amo = (w / 2 - bw / 2, 6)
    kb = (w - bw, h - bh - 6)
    llm = (w - bw, h / 2 - bh / 2 - 8)
    node(c, *api, bw, bh, "app/api", tr("HTTP, проверка запроса,\nкоды ошибок", "HTTP, request checks,\nerror codes"), ORANGE_L, ORANGE, 10, 7.6)
    node(c, *core, bw, bh, "app/core", tr("pipeline, промпт,\nзащитные проверки", "pipeline, prompt,\nguards"), BLUE_L, BLUE, 10, 7.6)
    node(c, *amo, bw, bh, "integrations/amocrm", tr("вебхуки, JWT,\nREST API v4", "webhooks, JWT,\nREST API v4"), VIOLET_L, VIOLET, 9.5, 7.6)
    node(c, *kb, bw, bh, "app/knowledge", tr("JSON, проверка,\nпоиск", "JSON, validation,\nretrieval"), TEAL_L, TEAL, 10, 7.6)
    node(c, *llm, bw, bh, "app/llm", tr("протокол LLMClient,\nHTTPX, повторы", "LLMClient protocol,\nHTTPX, retries"), GREEN_L, GREEN, 10, 7.6)
    arrow(c, api[0] + bw + 2, api[1] + bh - 6, core[0] - 2, core[1] + bh / 2)
    arrow(c, api[0] + bw + 2, api[1] + 6, amo[0] - 2, amo[1] + bh / 2)
    arrow(c, core[0] + bw + 2, core[1] + bh / 2, kb[0] - 2, kb[1] + bh / 2)
    arrow(c, core[0] + bw + 2, core[1] + 8, llm[0] - 2, llm[1] + bh - 8)
    poly_arrow(c, [(amo[0] + bw / 2, amo[1] + bh + 1), (amo[0] + bw / 2, core[1] - 2)], dash=[3, 2])
    c.setFillColor(MUTED)
    draw_text(c, amo[0] + bw / 2 + 6, (amo[1] + bh + core[1]) / 2 - 3, tr("DialogContext, dialog.py", "DialogContext, dialog.py"), "PT-Italic", 7.6)


def kb_reload_flow(c, w, h):
    """Как репозиторий решает, перечитать ли файл и что делать с ошибкой."""
    bh = 46
    y = h - bh
    node(c, 0, y, 96, bh, "repo.get()", tr("при каждом\nзапросе", "on every\nrequest"), SOFT, LINE, 9.5, 7.6)
    node(c, 116, y, 110, bh, tr("mtime изменился?", "mtime changed?"), tr("один вызов stat()", "one stat() call"), BLUE_L, BLUE, 9.5, 7.6)
    node(c, 246, y, 110, bh, tr("Прочитать и\nпроверить", "Read and\nvalidate"), "KnowledgeBase", TEAL_L, TEAL, 9.5, 7.6)
    node(c, 376, y + 26, w - 376, bh - 18, tr("Заменить версию", "Replace version"), "", GREEN_L, GREEN, 9, 7)
    node(c, 376, y - 26, w - 376, bh + 4, tr("Оставить прошлую", "Keep the previous one"), tr("last_error → /health\nstatus: degraded", "last_error → /health\nstatus: degraded"), ORANGE_L, ORANGE, 9, 7.4)
    arrow(c, 98, y + bh / 2, 114, y + bh / 2)
    arrow(c, 228, y + bh / 2, 244, y + bh / 2)
    c.setFillColor(MUTED)
    draw_text(c, 230, y + bh / 2 + 4, tr("да", "yes"), "PT-Bold", 7.4)
    arrow(c, 358, y + bh / 2 + 6, 374, y + bh - 6)
    arrow(c, 358, y + bh / 2 - 6, 374, y + 6)
    poly_arrow(c, [(171, y - 1), (171, 8), (48, 8), (48, y - 1)], dash=[3, 2])
    c.setFillColor(MUTED)
    draw_text(c, 60, 12, tr("нет — вернуть текущую версию из памяти", "no — return the cached version"), "PT-Italic", 7.6)


def score_bars(results, c, w, h):
    """Горизонтальные полосы оценок поиска; связанные позиции — пунктиром."""
    label_w, row_h = 150, 15
    top = max((score for _, score, _ in results), default=1) or 1
    for index, (item_id, score, reason) in enumerate(results):
        y = h - (index + 1) * row_h
        c.setFillColor(TEXT)
        draw_text(c, 0, y + 4, item_id, "Mono", 7.8)
        bar_w = (w - label_w - 40) * score / top
        if reason == "related":
            rbox(c, label_w, y + 2, 60, row_h - 5, WHITE, VIOLET, r=2, lw=0.8, dash=[2, 2])
            c.setFillColor(VIOLET)
            draw_text(c, label_w + 66, y + 4, tr("связанная", "related"), "PT-Italic", 7.6)
        else:
            rbox(c, label_w, y + 2, max(bar_w, 2), row_h - 5, TEAL if index == 0 else TEAL_L, None, r=2)
            c.setFillColor(TEXT)
            draw_text(c, label_w + max(bar_w, 2) + 5, y + 4, f"{score:.3f}", "Mono", 7.6)


def prompt_blocks(c, w, h):
    """Из чего состоит промпт: доверенные правила и недоверенные данные клиента."""
    left_w = 170
    node(c, 0, 0, left_w, h, "system", tr(
        "роль: ассистент менеджера\nфакты только из базы\nбезопасность\nправила ответа клиенту\nправила подсказки\nсхема JSON",
        "role: manager's assistant\nfacts only from the KB\nsafety\ncustomer reply rules\nmanager hint rules\nJSON schema",
    ), BLUE_L, BLUE, 11, 8)
    blocks = [
        ("<knowledge_base>", tr("факты найденных позиций", "facts of matched items"), TEAL_L, TEAL),
        ("<catalog>", tr("только названия, без цен", "names only, no prices"), TEAL_L, TEAL),
        ("<client_info>", tr("имя клиента", "customer name"), ORANGE_L, ORANGE),
        ("<dialog_history>", tr("история, ПДн замаскированы", "history, PII masked"), ORANGE_L, ORANGE),
        ("<customer_message>", tr("сообщение, теги вырезаны", "message, tags removed"), ORANGE_L, ORANGE),
    ]
    x = left_w + 26
    bw = w - x
    gap = 5
    bh = (h - 18 - gap * (len(blocks) - 1)) / len(blocks)
    c.setFillColor(MUTED)
    draw_text(c, x, h - 9, "user", "PT-Bold", 9)
    for index, (title, sub, fill, edge) in enumerate(blocks):
        y = h - 16 - (index + 1) * bh - index * gap
        rbox(c, x, y, bw, bh, fill, edge, r=5, lw=0.9)
        c.setFillColor(INK)
        draw_text(c, x + 8, y + bh / 2 - 3, title, "Mono-Bold", 8.4)
        c.setFillColor(MUTED)
        draw_text(c, x + 140, y + bh / 2 - 3, sub, "PT", 8.2)
    c.setFillColor(ORANGE)
    c.saveState()
    c.translate(x - 12, 6)
    c.rotate(90)
    draw_text(c, 0, 0, tr("данные клиента — не инструкции", "customer data — not instructions"), "PT-Bold", 7.6)
    c.restoreState()


def retry_timeline(c, w, h):
    """Три попытки запроса к модели и задержки между ними."""
    y = h / 2
    x0, x1 = 20, w - 20
    c.setStrokeColor(LINE)
    c.setLineWidth(1.2)
    c.line(x0, y, x1, y)
    marks = [
        (x0 + 30, tr("попытка 1", "attempt 1"), "ConnectError / 503", ORANGE),
        (x0 + 190, tr("попытка 2", "attempt 2"), tr("через 0,5 с", "after 0.5 s"), ORANGE),
        (x0 + 350, tr("попытка 3", "attempt 3"), tr("через 1 с", "after 1 s"), ORANGE),
    ]
    for x, title, sub, color in marks:
        circle_num(c, x, y, 9, "!", color, WHITE, 9)
        c.setFillColor(INK)
        draw_text(c, x, y + 16, title, "PT-Bold", 8.6, "center")
        c.setFillColor(MUTED)
        draw_text(c, x, y - 22, sub, "PT", 8, "center")
    node(c, x1 - 70, y - 20, 70, 40, "503", "llm_unavailable", ORANGE_L, ORANGE, 11, 7.4)
    arrow(c, x0 + 350 + 12, y, x1 - 72, y)


def repair_flow(c, w, h):
    """Разбор ответа модели и одна попытка починки."""
    bh = 44
    y = h - bh - 4
    items = [
        (tr("Ответ модели", "Model answer"), tr("текст", "text"), SOFT, LINE),
        (tr("Снять ```json", "Strip ```json"), tr("и найти { … }", "and find { … }"), BLUE_L, BLUE),
        ("json.loads", tr("объект?", "an object?"), BLUE_L, BLUE),
        ("Suggestion", tr("схема и типы", "schema and types"), TEAL_L, TEAL),
    ]
    gap = 14
    bw = (w - 3 * gap - 90) / 4
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, y, bw, bh, title, sub, fill, edge, 9.2, 7.6)
        if index:
            arrow(c, x - gap + 1, y + bh / 2, x - 1, y + bh / 2)
    ok_x = 4 * (bw + gap) - gap + 14
    node(c, ok_x, y, w - ok_x, bh, "OK", tr("дальше — пост-проверки", "then post-checks"), GREEN_L, GREEN, 10, 7.4)
    arrow(c, ok_x - 13, y + bh / 2, ok_x - 1, y + bh / 2)
    ry = 6
    node(c, 60, ry, 200, 40, tr("REPAIR_PROMPT: «ошибки в полях: …»", "REPAIR_PROMPT: «field errors: …»"), tr("один повторный запрос", "one more request"), AMBER_L, AMBER, 8.6, 7.4)
    node(c, 300, ry, 160, 40, "502 llm_invalid_output", tr("если и второй ответ плохой", "if the second answer fails too"), ORANGE_L, ORANGE, 8.6, 7.4)
    last_center = 3 * (bw + gap) + bw / 2
    poly_arrow(c, [(last_center, y - 1), (last_center, ry + 54), (160, ry + 54), (160, ry + 41)], AMBER)
    c.setFillColor(AMBER)
    draw_text(c, last_center + 4, y - 14, tr("ошибка", "error"), "PT-Bold", 7.4)
    arrow(c, 262, ry + 20, 298, ry + 20, ORANGE)


def guards_flow(c, w, h):
    """Пост-проверки по порядку."""
    items = [
        ("enforce_upsell_rules", tr("позиция есть в базе? название — из базы;\nнеуместно → поля null", "item exists? name from the KB;\nnot applicable → fields null"), VIOLET_L, VIOLET),
        ("strip_internal_leaks", tr("из ответа клиенту — служебные\nслова и копии подсказки", "remove internal words and hint\ncopies from the customer reply"), ORANGE_L, ORANGE),
        ("find_unverified_amounts", tr("₽ и % не из базы и не из переписки\n→ предупреждение", "₽ and % not in KB or conversation\n→ warning"), AMBER_L, AMBER),
    ]
    gap = 16
    bw = (w - 2 * gap) / 3
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, 0, bw, h, title, sub, fill, edge, 9, 7.8, sub_font="PT")
        if index:
            arrow(c, x - gap + 1, h / 2, x - 1, h / 2)


def separation_layers(c, w, h):
    """Четыре уровня, которые держат подсказку отдельно от ответа клиенту."""
    layers = [
        (tr("1 · Контракт", "1 · Contract"), tr("разные поля JSON: customer_reply и upsell_*", "separate JSON fields: customer_reply and upsell_*"), BLUE_L, BLUE),
        (tr("2 · Промпт", "2 · Prompt"), tr("правило: не вставлять допродажу и служебные слова", "rule: no upsell or internal words in the reply"), TEAL_L, TEAL),
        (tr("3 · Сервер", "3 · Server"), tr("strip_internal_leaks() вырезает нарушения", "strip_internal_leaks() removes violations"), ORANGE_L, ORANGE),
        (tr("4 · Интерфейс", "4 · Interface"), tr("отдельный блок «не отправлять клиенту», нет автоотправки", "separate «do not send» block, no auto-send"), GREEN_L, GREEN),
    ]
    gap = 6
    bh = (h - gap * 3) / 4
    for index, (title, sub, fill, edge) in enumerate(layers):
        y = h - (index + 1) * bh - index * gap
        rbox(c, 0, y, w, bh, fill, edge, r=6, lw=1)
        c.setFillColor(INK)
        draw_text(c, 12, y + bh / 2 - 3.5, title, "PT-Bold", 10)
        c.setFillColor(TEXT)
        draw_text(c, 130, y + bh / 2 - 3.5, sub, "PT", 9)


def injection_layers(c, w, h):
    """Слои защиты от prompt injection."""
    layers = [
        (tr("Очистка входа", "Input sanitising"), tr("теги промпта и управляющие\nсимволы вырезаются", "prompt tags and control\ncharacters removed"), ORANGE_L, ORANGE),
        (tr("Изоляция", "Isolation"), tr("данные — в блоках с пометкой\n«не инструкции»", "data in blocks marked\n«not instructions»"), BLUE_L, BLUE),
        (tr("Детектор", "Detector"), tr("5 групп правил → предупреждение\nменеджеру и модели", "5 rule groups → warning\nfor manager and model"), VIOLET_L, VIOLET),
        (tr("Нет инструментов", "No tools"), tr("модель только пишет текст,\nничего не отправляет", "the model only writes text,\nsends nothing"), TEAL_L, TEAL),
        (tr("Человек", "Human"), tr("менеджер читает каждый\nответ перед отправкой", "the manager reads every\nreply before sending"), GREEN_L, GREEN),
    ]
    gap = 9
    bw = (w - gap * 4) / 5
    for index, (title, sub, fill, edge) in enumerate(layers):
        x = index * (bw + gap)
        node(c, x, 0, bw, h, title, sub, fill, edge, 9.4, 7.6)
        circle_num(c, x + 9, h - 9, 6.5, str(index + 1), edge, WHITE, 7.5)


def ui_wireframe(c, w, h):
    """Макет страницы менеджера."""
    rbox(c, 0, 0, w, h, SOFT, LINE, r=8, lw=0.8)
    left_w = w * 0.42
    pad = 10
    # Левая колонка
    rbox(c, pad, pad, left_w - pad * 1.5, h - pad * 2, WHITE, LINE, r=6, lw=0.6)
    lx = pad + 10
    y = h - pad - 20
    c.setFillColor(INK)
    draw_text(c, lx, y, tr("Переписка", "Conversation"), "PT-Bold", 9.5)
    fields = [
        (tr("Сообщение клиента *", "Customer message *"), 40),
        (tr("История переписки", "Conversation history"), 50),
        (tr("Имя клиента", "Customer name"), 16),
    ]
    y -= 8
    for label, fh in fields:
        y -= 12
        c.setFillColor(MUTED)
        draw_text(c, lx, y, label, "PT-Bold", 7.4)
        y -= fh + 4
        rbox(c, lx, y, left_w - pad * 1.5 - 20, fh, WHITE, LINE, r=3, lw=0.6)
    y -= 26
    rbox(c, lx, y, 150, 18, BLUE, None, r=4)
    c.setFillColor(WHITE)
    draw_text(c, lx + 75, y + 6, tr("Сгенерировать рекомендации", "Generate suggestions"), "PT-Bold", 7.6, "center")
    y -= 22
    for index, label in enumerate([tr("Покупка", "Purchase"), tr("Мало информации", "Too little info"), tr("Жалоба", "Complaint"), "Injection"]):
        cw = pdfmetrics.stringWidth(label, "PT", 7) + 10
        offsets = [0, 46, 0, 46]
        rbox(c, lx + (0 if index % 2 == 0 else 52 + offsets[index]), y - (index // 2) * 16, cw, 12, SOFT, LINE, r=6, lw=0.5)
        c.setFillColor(TEXT)
        draw_text(c, lx + (0 if index % 2 == 0 else 52 + offsets[index]) + 5, y - (index // 2) * 16 + 3.5, label, "PT", 7)
    # Правая колонка
    rx = left_w + pad / 2
    rw = w - rx - pad
    rbox(c, rx, pad, rw, h - pad * 2, WHITE, LINE, r=6, lw=0.6)
    inner = rx + 10
    iw = rw - 20
    y = h - pad - 26
    rbox(c, inner, y, iw, 16, AMBER_L, AMBER, r=3, lw=0.6)
    c.setFillColor(INK)
    draw_text(c, inner + 6, y + 5, tr("Проверьте перед отправкой", "Check before sending"), "PT-Bold", 7.4)
    y -= 78
    rbox(c, inner, y, iw, 70, WHITE, LINE, r=4, lw=0.6)
    c.setFillColor(BLUE)
    c.rect(inner, y, 3, 70, stroke=0, fill=1)
    c.setFillColor(INK)
    draw_text(c, inner + 10, y + 58, tr("Ответ клиенту", "Customer reply"), "PT-Bold", 8.6)
    for row in range(3):
        rbox(c, inner + 10, y + 40 - row * 10, iw - 30 - row * 30, 5, SLATE_L, None, r=2)
    rbox(c, inner + iw - 62, y + 6, 54, 13, BLUE, None, r=3)
    c.setFillColor(WHITE)
    draw_text(c, inner + iw - 35, y + 10, tr("Копировать", "Copy"), "PT-Bold", 7, "center")
    y -= 92
    rbox(c, inner, y, iw, 84, AMBER_L, None, r=4)
    c.setFillColor(AMBER)
    c.rect(inner, y, 3, 84, stroke=0, fill=1)
    c.setFillColor(INK)
    draw_text(c, inner + 10, y + 72, tr("Подсказка менеджеру", "Manager hint"), "PT-Bold", 8.6)
    chip(c, inner + 110, y + 69, tr("только для вас", "internal only"), AMBER, WHITE, "PT-Bold", 6.8)
    c.setFillColor(GREEN)
    draw_text(c, inner + 10, y + 56, tr("Допродажа уместна", "Upsell appropriate"), "PT-Bold", 7.6)
    c.setFillColor(MUTED)
    draw_text(c, inner + 10, y + 43, tr("Предложить · Почему", "Offer · Why"), "PT", 7.4)
    rbox(c, inner + 10, y + 8, iw - 20, 28, WHITE, AMBER, r=3, lw=0.6, dash=[2, 2])
    c.setFillColor(MUTED)
    draw_text(c, inner + 16, y + 19, tr("Пример фразы для клиента", "Sample phrase"), "PT-Italic", 7.2)


def log_layers(c, w, h):
    """Три слоя, которые не пускают ПДн и секреты в логи."""
    items = [
        (tr("Код", "Code"), tr("в сообщениях только id,\nсчётчики, коды, время", "messages hold only ids,\ncounters, codes, timing"), BLUE_L, BLUE),
        ("RedactingFilter", tr("маскирует Bearer, token=,\nsk-…, JWT, e-mail, телефон", "masks Bearer, token=,\nsk-…, JWT, e-mail, phone"), VIOLET_L, VIOLET),
        ("AccessLogFilter", tr("IP → «-», путь без\nquery string (?secret=…)", "IP → «-», path without\nquery string (?secret=…)"), TEAL_L, TEAL),
    ]
    gap = 16
    bw = (w - 2 * gap) / 3
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, 0, bw, h, title, sub, fill, edge, 10, 8)
        if index:
            arrow(c, x - gap + 1, h / 2, x - 1, h / 2)


def amocrm_sequence(c, w, h):
    """Последовательность: вебхук, вызов из виджета, ответ менеджеру."""
    actors = [
        (tr("Клиент", "Customer"), ORANGE_L, ORANGE),
        ("amoCRM", BLUE_L, BLUE),
        (tr("Бэкенд", "Backend"), TEAL_L, TEAL),
        (tr("Виджет", "Widget"), VIOLET_L, VIOLET),
        ("LLM", GREEN_L, GREEN),
    ]
    head_h, head_w = 24, 82
    step = (w - head_w) / (len(actors) - 1)
    xs = [head_w / 2 + i * step for i in range(len(actors))]
    for x, (name, fill, edge) in zip(xs, actors, strict=True):
        node(c, x - head_w / 2, h - head_h, head_w, head_h, name, "", fill, edge, 9.5)
        c.setStrokeColor(LINE)
        c.setDash([2, 2])
        c.line(x, h - head_h, x, 0)
        c.setDash([])
    messages = [
        (0, 1, tr("сообщение в чат", "chat message"), ORANGE),
        (1, 2, tr("вебхук message[add] → кэш (< 2 с)", "webhook message[add] → cache (< 2 s)"), BLUE),
        (3, 2, tr("«Сгенерировать»: $authorizedAjax + JWT", "«Generate»: $authorizedAjax + JWT"), VIOLET),
        (2, 1, "GET /api/v4/leads/{id}?with=contacts", TEAL),
        (2, 4, tr("промпт → JSON", "prompt → JSON"), TEAL),
        (2, 3, tr("ответ клиенту + подсказка", "reply + hint"), TEAL),
        (3, 1, tr("менеджер копирует и отправляет", "manager copies and sends"), VIOLET),
    ]
    y = h - head_h - 18
    gap = (h - head_h - 26) / len(messages)
    for src, dst, label, color in messages:
        x1, x2 = xs[src], xs[dst]
        arrow(c, x1, y, x2 + (-3 if x2 > x1 else 3), y, color, 1.1, 5)
        # Белая подложка: пунктир участников не должен перечёркивать подпись.
        label_w = pdfmetrics.stringWidth(label, "PT", 7.6) + 8
        c.setFillColor(WHITE)
        c.rect((x1 + x2) / 2 - label_w / 2, y + 2, label_w, 10, stroke=0, fill=1)
        c.setFillColor(TEXT)
        draw_text(c, (x1 + x2) / 2, y + 4, label, "PT", 7.6, "center")
        y -= gap


def jwt_checks(c, w, h):
    """Четыре проверки одноразового токена виджета."""
    items = [
        (tr("Подпись HS256", "HS256 signature"), tr("секретный ключ\nинтеграции", "integration\nsecret key"), BLUE_L, BLUE),
        ("exp / nbf", tr("срок действия,\nдопуск 30 с", "validity,\n30 s leeway"), TEAL_L, TEAL),
        ("client_uuid", tr("= AMOCRM_\nCLIENT_ID", "= AMOCRM_\nCLIENT_ID"), VIOLET_L, VIOLET),
        (tr("Хост iss", "iss host"), tr("= хост\nAMOCRM_BASE_URL", "= host of\nAMOCRM_BASE_URL"), AMBER_L, AMBER),
    ]
    gap = 12
    end_w = 82
    bw = (w - end_w - gap * 4) / 4
    for index, (title, sub, fill, edge) in enumerate(items):
        x = index * (bw + gap)
        node(c, x, 0, bw, h, title, sub, fill, edge, 9.4, 7.6)
        arrow(c, x + bw + 1, h / 2, x + bw + gap - 1, h / 2)
    node(c, w - end_w, h / 2 + 2, end_w, h / 2 - 2, "WidgetUser", "account_id, user_id", GREEN_L, GREEN, 8.8, 6.8)
    node(c, w - end_w, 0, end_w, h / 2 - 6, "401", tr("любая не прошла", "any failed"), ORANGE_L, ORANGE, 9, 6.8)


def adapter_flow(c, w, h):
    """Draw three separated outcomes for the current message and history."""
    bh = 44
    node(c, 0, h - bh, 150, bh, tr("Текст в поле виджета?", "Text in widget field?"), "", BLUE_L, BLUE, 9.4)
    node(c, 200, h - bh, w - 200, bh, tr("да → это сообщение (manual)", "yes → this is the message (manual)"), tr("такой же последний в кэше — убрать из истории", "same as last cached — drop from history"), GREEN_L, GREEN, 9, 7.4)
    node(c, 200, h - 2 * bh - 14, w - 200, bh, tr("нет → последние подряд сообщения клиента (webhook)", "no → trailing customer messages (webhook)"), tr("«18 метров.» + «Сколько с установкой?» = одно обращение", "«18 m².» + «How much installed?» = one request"), TEAL_L, TEAL, 9, 7.4)
    node(c, 200, 0, w - 200, bh - 6, tr("нет сообщений клиента → 422 amocrm_no_message", "no customer messages → 422 amocrm_no_message"), "", ORANGE_L, ORANGE, 8.8)
    arrow(c, 152, h - bh / 2, 198, h - bh / 2)
    poly_arrow(c, [(75, h - bh - 1), (75, h - 1.5 * bh - 14), (198, h - 1.5 * bh - 14)])
    poly_arrow(c, [(75, h - 1.5 * bh - 14), (75, (bh - 6) / 2), (198, (bh - 6) / 2)], dash=[3, 2])


def access_flow(c, w, h):
    """Путь запроса через защиту: публичный путь, HTTP Basic, лимит, pipeline."""
    bh = 46
    y = h - bh - 18  # сверху — место для ветки «публичный путь»
    items = [
        (tr("Запрос", "Request"), tr("UI, API или виджет", "UI, API or widget"), SOFT, LINE),
        (tr("Публичный путь?", "Public path?"), tr("/health,\n/api/v1/amocrm/*", "/health,\n/api/v1/amocrm/*"), BLUE_L, BLUE),
        ("HTTP Basic", tr("если задан\nUI_BASIC_AUTH_*", "if UI_BASIC_AUTH_*\nis set"), VIOLET_L, VIOLET),
        ("RateLimiter", tr("IP или пользователь\namoCRM, окно 60 с", "IP or amoCRM user,\n60 s window"), AMBER_L, AMBER),
        ("Pipeline", tr("LLM-генерация", "LLM generation"), GREEN_L, GREEN),
    ]
    gap = 14
    bw = (w - gap * 4) / 5
    xs = [index * (bw + gap) for index in range(len(items))]
    for x, (title, sub, fill, edge) in zip(xs, items, strict=True):
        node(c, x, y, bw, bh, title, sub, fill, edge, 9.2, 7.4)
        if x:
            arrow(c, x - gap + 1, y + bh / 2, x - 1, y + bh / 2)
    for index, code, label in ((2, "401", "unauthorized"), (3, "429", "rate_limited")):
        node(c, xs[index], 0, bw, 30, code, label, ORANGE_L, ORANGE, 9, 7)
        arrow(c, xs[index] + bw / 2, y - 1, xs[index] + bw / 2, 31, ORANGE)
    top = y + bh + 10
    poly_arrow(
        c,
        [(xs[1] + bw / 2, y + bh + 1), (xs[1] + bw / 2, top), (xs[3] + bw / 2, top), (xs[3] + bw / 2, y + bh + 1)],
        BLUE,
        dash=[3, 2],
    )
    c.setFillColor(BLUE)
    draw_text(c, (xs[1] + xs[3] + bw) / 2, top + 3, tr("да: без пароля, своя защита", "yes: no login, own protection"), "PT-Italic", 7.2, "center")
