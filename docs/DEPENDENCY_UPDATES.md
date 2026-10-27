# Обновление Python-зависимостей

[README](../README.md) · [CI and delivery](instructions/ci-and-delivery.md) ·
[Версии и выпуск](RELEASES.md)

Здесь описано, какие зависимости закреплены, как их обновлять и как
проверять на известные уязвимости. Автоматических PR с обновлениями у
проекта **нет** — обновление делается вручную по шагам ниже.

## Что закреплено

| Файл | Пакеты | Для чего |
| --- | --- | --- |
| `requirements.txt` | `fastapi==0.151.0`, `uvicorn[standard]==0.54.0`, `pydantic==2.14.1`, `pydantic-settings==2.16.0`, `httpx==0.28.1`, `pyjwt==2.15.1` | Приложение; ставится в Docker-образ |
| `requirements-dev.txt` | `-r requirements.txt` + `pytest==9.1.1`, `ruff==0.17.1`, `mypy==2.4.0` | Проверки локально и в CI |
| `requirements-guide.txt` | `-r requirements-dev.txt` + `reportlab==4.4.9` | Сборка PDF-руководства |
| `.github/workflows/ci.yml` | `actions/checkout` и `actions/setup-python` v7.0.0, закреплены полным SHA | CI |

Точные версии (`==`) стоят только у **прямых** зависимостей. Их собственные
зависимости (Starlette, AnyIO, Pydantic Core и другие) pip выбирает при
каждой установке заново, поэтому две установки в разные дни могут различаться.
В соседних проектах AI Forge это решено файлом `uv.lock`; здесь его пока нет
([ADR 0001](adr/0001-application-layout-and-tooling.md)).

## Проверить на известные уязвимости

Разово, без добавления инструмента в проект:

```bash
uv run --no-project --with pip-audit pip-audit -r requirements-dev.txt -r requirements-guide.txt
```

Фактический результат проверки 27 октября 2026 года:

```text
No known vulnerabilities found
```

pip-audit заново разрешает дерево зависимостей и сверяет его с базой
уязвимостей PyPI, поэтому нужна сеть, а результат относится к дате запуска.
Если уязвимость найдена — обновите пакет до исправленной версии по шагам
ниже; если исправления нет, запишите исключение с причиной и сроком
пересмотра в [журнал](DEVELOPMENT_LOG.md).

## Как обновить

1. Создайте чистое окружение — старое могло накопить лишние пакеты:

   ```bash
   python3.12 -m venv /tmp/deps-check
   /tmp/deps-check/bin/python -m pip install -r requirements-guide.txt
   /tmp/deps-check/bin/python -m pip list --outdated
   ```

2. Обновляйте по одному пакету или небольшой группе связанных (например,
   `fastapi` вместе с `pydantic`): так понятно, что именно сломало проверку.
   Поменяйте номер в нужном `requirements*.txt`.
3. Установите обновлённые зависимости в рабочее окружение и выполните шесть
   проверок CI:

   ```bash
   .venv/bin/python -m pip install -r requirements-guide.txt
   .venv/bin/python -m ruff check app tests scripts evals
   .venv/bin/python -m mypy app evals
   .venv/bin/python -m pytest
   .venv/bin/python scripts/run_evals.py retrieval
   .venv/bin/python scripts/check_docs.py
   .venv/bin/python scripts/build_widget.py
   ```

4. Если обновлялись пакеты приложения — соберите образ и проверьте контейнер
   ([Версии и выпуск](RELEASES.md#4-как-собрать-и-проверить-образ-версии)).
5. Если обновлялся ReportLab или менялись версии в руководстве — пересоберите
   PDF и просмотрите все страницы ([инструкция](guide/README.md)).
6. Запишите обновление в [журнал](DEVELOPMENT_LOG.md) и закоммитьте одним
   коммитом: `Update fastapi to 0.152.0` и т. п.

## На что обратить внимание

| Пакет | Риск при обновлении |
| --- | --- |
| `fastapi`, `starlette` | Starlette 1.x уже убрала часть старых API; следите за предупреждениями — в тестах предупреждения об устаревании из `app` превращены в ошибки |
| `pydantic`, `pydantic-settings` | Тексты ошибок валидации используются в документации; формат `.env` (`env_ignore_empty`, `env_parse_none_str`) |
| `httpx` | `MockTransport` в тестах; Starlette предупреждает, что её `TestClient` предпочитает `httpx2` — приложение по ТЗ использует `httpx`, предупреждение скрыто только в тестах |
| `pyjwt` | Проверка подписи токена виджета: тесты `test_widget_rejects_invalid_tokens` должны остаться зелёными |
| `ruff`, `mypy` | Новые версии находят новые ошибки: это нормально, исправьте код, не ослабляя правила целиком |

## Обновление действий GitHub Actions

Действия закреплены полным SHA коммита, рядом — номер версии в комментарии.
Чтобы обновить, найдите тег новой версии в репозитории действия, возьмите
SHA его коммита и замените оба значения. Тег можно передвинуть, SHA — нет,
поэтому закрепление по SHA защищает от подмены действия.

## Чего пока нет

- Автоматических еженедельных PR с обновлениями, как в AI Support Agent.
- Проверки уязвимостей в CI: `pip-audit` запускается только вручную.
- Файла блокировки всего дерева зависимостей (`uv.lock`).
