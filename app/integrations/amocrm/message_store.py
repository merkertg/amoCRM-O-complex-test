"""Кэш последних сообщений чатов, полученных через вебхуки amoCRM.

Почему кэш: REST API amoCRM не отдаёт тексты сообщений из чатов
(API бесед и событий возвращают только идентификаторы), а API чатов
доступен лишь для собственного канала. Тексты приходят только
в вебхуках `message` (входящие) и `outgoing_message` (исходящие).

Хранилище намеренно простое: в памяти процесса, ограничено по числу
сообщений на сделку/контакт и по времени жизни (TTL), чтобы не копить
персональные данные. При перезапуске кэш очищается. Для нескольких
воркеров или реплик его нужно заменить на Redis с тем же интерфейсом.
"""

import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass

from app.schemas import Role


@dataclass(frozen=True)
class StoredMessage:
    message_id: str
    role: Role
    text: str
    created_at: int
    lead_id: int | None = None
    contact_id: int | None = None
    talk_id: int | None = None


class MessageStore:
    def __init__(self, max_per_key: int = 30, ttl_seconds: int = 24 * 3600, max_keys: int = 5000) -> None:
        self._max_per_key = max_per_key
        self._ttl = ttl_seconds
        self._max_keys = max_keys
        self._lock = threading.Lock()
        self._by_key: OrderedDict[str, deque[StoredMessage]] = OrderedDict()
        self._seen: OrderedDict[str, None] = OrderedDict()

    def add(self, message: StoredMessage) -> bool:
        """Сохраняет сообщение. Повторная доставка того же вебхука игнорируется."""
        with self._lock:
            if message.message_id in self._seen:
                return False
            self._seen[message.message_id] = None
            while len(self._seen) > self._max_keys * self._max_per_key:
                self._seen.popitem(last=False)
            keys = []
            if message.lead_id:
                keys.append(f"lead:{message.lead_id}")
            if message.contact_id:
                keys.append(f"contact:{message.contact_id}")
            for key in keys:
                bucket = self._by_key.setdefault(key, deque(maxlen=self._max_per_key))
                bucket.append(message)
                self._by_key.move_to_end(key)
            while len(self._by_key) > self._max_keys:
                self._by_key.popitem(last=False)
            return bool(keys)

    def _get(self, key: str) -> list[StoredMessage]:
        threshold = time.time() - self._ttl
        with self._lock:
            bucket = self._by_key.get(key)
            if not bucket:
                return []
            fresh = [m for m in bucket if m.created_at >= threshold]
            if len(fresh) != len(bucket):
                self._by_key[key] = deque(fresh, maxlen=self._max_per_key)
        return sorted(fresh, key=lambda m: m.created_at)

    def for_lead(self, lead_id: int) -> list[StoredMessage]:
        return self._get(f"lead:{lead_id}")

    def for_contact(self, contact_id: int) -> list[StoredMessage]:
        return self._get(f"contact:{contact_id}")

    def clear(self) -> None:
        with self._lock:
            self._by_key.clear()
            self._seen.clear()
