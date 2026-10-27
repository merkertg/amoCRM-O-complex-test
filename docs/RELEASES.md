# Версии и выпуск сервиса и виджета

[README](../README.md) · [CI and delivery](instructions/ci-and-delivery.md) ·
[amoCRM integration](instructions/amocrm.md) · [Восстановление после сбоев](RECOVERY.md)

У проекта две независимые поставки: **сервис** (FastAPI в Docker на вашем
сервере) и **виджет amoCRM** (архив `widget.zip`, который загружают в
интеграцию). Автоматической публикации нет: CI проверяет код и собирает
архив виджета, но ничего не выкладывает. В репозитории пока нет ни одного
тега версии — выпуск `1.0.0` существует только как номер в файлах.

## 1. Где записаны версии

| Что | Где | Сейчас | Где видна |
| --- | --- | --- | --- |
| Версия проекта | `pyproject.toml` → `[project] version` | `1.0.0` | Метаданные проекта |
| Версия API | `app/main.py` → `FastAPI(version=...)` | `1.0.0` | `/docs`, `/openapi.json` → `info.version` |
| Версия виджета | `amocrm_widget/manifest.json` → `widget.version` | `1.0.0` | Карточка интеграции в amoCRM; вывод `scripts/build_widget.py` |
| Образ Docker | `docker-compose.yml` → `image` | `amocrm-sales-assistant:latest` | `docker images` |

Версия проекта и версия API меняются вместе: это один сервис. Версия
виджета меняется только при изменении файлов в `amocrm_widget/` —
amoCRM требует новый номер при каждой загрузке архива.

Схема номеров — `MAJOR.MINOR.PATCH`:

| Изменение | Пример | Номер |
| --- | --- | --- |
| Несовместимое изменение API: виджет старой версии перестанет работать | Переименовано поле ответа `suggestion` | `2.0.0` |
| Новая возможность без поломки существующих клиентов | Новый эндпоинт, новая настройка | `1.1.0` |
| Исправление без изменения API | Поправлены ключевые слова, исправлена проверка сумм | `1.0.1` |

Правка только базы знаний (`data/knowledge_base.json`) выпуска не требует:
файл подхватывается без перезапуска (см. [Knowledge base](instructions/knowledge-base.md)).

## 2. Что проверить до выпуска

Все команды выполняются из корня проекта.

```bash
git status --short
git fetch origin && git status -sb
```

Первая команда должна закончиться без вывода (нет незакоммиченных
изменений), вторая — показать, что `main` совпадает с `origin/main`.

Затем шесть проверок CI локально:

```bash
.venv/bin/python -m ruff check app tests scripts evals
.venv/bin/python -m mypy app evals
.venv/bin/python -m pytest
.venv/bin/python scripts/run_evals.py retrieval
.venv/bin/python scripts/check_docs.py
.venv/bin/python scripts/build_widget.py
```

И то, чего CI не делает:

- открыть [Actions](https://github.com/merkertg/amoCRM-O-complex-test/actions)
  и убедиться, что запуск для этого коммита зелёный — локальный успех его
  не заменяет;
- собрать образ и проверить контейнер (раздел 4);
- если менялись промпт, поиск или модель — прогнать
  `scripts/run_evals.py dialogues` с настоящей моделью
  ([Quality evaluations](instructions/evaluations.md));
- если менялся учебный материал — пересобрать PDF по
  [инструкции](guide/README.md).

## 3. Как выпустить версию

Пример для `1.1.0`; подставьте свой номер.

1. Поменяйте версию в `pyproject.toml` и в `app/main.py`; если менялся
   виджет — и в `amocrm_widget/manifest.json`.
2. Запишите выпуск в [журнал](DEVELOPMENT_LOG.md), а фактические проверки —
   в [отчёт](VERIFICATION.md).
3. Закоммитьте и отправьте:

   ```bash
   git commit -am "Release 1.1.0"
   git push origin main
   ```

4. Дождитесь зелёного CI для этого коммита, затем поставьте тег с описанием
   и отправьте его. Занятый тег не перезаписывайте — выберите следующий номер.

   ```bash
   git tag -l v1.1.0
   git tag -a v1.1.0 -m "AI Sales Assistant 1.1.0"
   git push origin v1.1.0
   ```

   Первая команда должна закончиться без вывода: такого тега ещё нет.

## 4. Как собрать и проверить образ версии

```bash
docker build -t amocrm-sales-assistant:1.1.0 .
docker run -d --rm --name assistant-release -p 18000:8000 amocrm-sales-assistant:1.1.0
curl -s http://127.0.0.1:18000/health
curl -s http://127.0.0.1:18000/openapi.json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
docker exec assistant-release id
docker stop assistant-release
```

Ожидается: `/health` → `"status":"ok"`, версия API — `1.1.0`, пользователь
контейнера — `uid=10001(appuser)`. Реестра образов у проекта нет: на сервере
образ собирают из того же тега (раздел 5).

## 5. Как обновить сервер

На сервере, в папке проекта, с готовым `.env`:

```bash
git fetch --tags
git checkout v1.1.0
docker compose up --build --detach
docker compose ps
curl -s http://127.0.0.1:8000/health
```

Во время пересоздания контейнера сервис недоступен несколько секунд.
После перезапуска кэш сообщений amoCRM и счётчики лимита пустые — так задумано;
что это значит для менеджеров, описано в [Восстановлении после сбоев](RECOVERY.md#перезапуск-сервиса).

## 6. Как выпустить новую версию виджета

1. Поднимите `widget.version` в `amocrm_widget/manifest.json`.
2. Соберите архив:

   ```bash
   .venv/bin/python scripts/build_widget.py
   ```

   ```text
   Готово: dist/widget.zip (версия 1.1.0)
   ```

3. В amoCRM: **амоМаркет** → интеграция → **режим редактирования** →
   загрузить `dist/widget.zip`. Ошибки в `manifest.json` amoCRM покажет сразу.
4. Откройте любую сделку и нажмите «Сгенерировать рекомендации».

`dist/` не хранится в Git. Чтобы откатить виджет, соберите архив из
предыдущего тега: `git checkout v1.0.1 -- amocrm_widget` и повторите шаги
2–3, затем верните файлы: `git checkout main -- amocrm_widget`.

## 7. Откат сервиса

```bash
git checkout v1.0.1
docker compose up --build --detach
curl -s http://127.0.0.1:8000/health
```

Сервис не хранит данных между версиями — базы данных нет, — поэтому откат
не требует миграций. База знаний лежит в `data/` и монтируется в контейнер:
её версия не зависит от версии сервиса. Перед правками базы знаний на
сервере делайте копию ([Резервное копирование](instructions/backup.md)).

## 8. Чего пока нет

| Возможность | Состояние |
| --- | --- |
| Сборка Docker-образа в CI | Нет: образ проверялся вручную на `df465b3` |
| Публикация образа в реестр (GHCR и т. п.) | Нет |
| Подпись образа и SBOM | Нет |
| Автоматический выпуск по тегу | Нет: тег и сборка — вручную по шагам выше |
| Проверка совпадения версий в `pyproject.toml` и `app/main.py` | Нет: следить вручную |
