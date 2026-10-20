"""Загрузка базы знаний из JSON с автоматической перезагрузкой.

База знаний редактируется без изменения кода: достаточно поправить JSON-файл.
Репозиторий сравнивает mtime файла при каждом обращении и перечитывает его,
если файл изменился. Если новая версия невалидна, продолжаем работать
с последней корректной и сохраняем текст ошибки для /health.
"""

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from app.errors import AppError
from app.knowledge.models import KnowledgeBase

logger = logging.getLogger(__name__)


class KnowledgeBaseError(AppError):
    """База знаний не загружена или повреждена."""

    status_code = 503
    code = "knowledge_base_unavailable"
    user_message = "База знаний недоступна: проверьте файл knowledge_base.json."


class KnowledgeBaseRepository:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._kb: KnowledgeBase | None = None
        self._mtime: float | None = None
        self.loaded_at: datetime | None = None
        self.last_error: str | None = None

    @property
    def path(self) -> Path:
        return self._path

    def get(self) -> KnowledgeBase:
        with self._lock:
            mtime = self._current_mtime()
            if self._kb is None or (mtime is not None and mtime != self._mtime):
                self._load(mtime)
            if self._kb is None:
                raise KnowledgeBaseError()
            return self._kb

    def _current_mtime(self) -> float | None:
        try:
            return self._path.stat().st_mtime
        except OSError:
            return None

    def _load(self, mtime: float | None) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            kb = KnowledgeBase.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            # Запоминаем mtime, чтобы не перечитывать сломанный файл на каждый запрос.
            self._mtime = mtime
            self.last_error = f"{type(exc).__name__}: {exc}"[:500]
            logger.error("knowledge base load failed: %s", type(exc).__name__)
            return
        self._kb = kb
        self._mtime = mtime
        self.loaded_at = datetime.now(UTC)
        self.last_error = None
        logger.info(
            "knowledge base loaded: products=%d faq=%d", len(kb.products), len(kb.faq)
        )
