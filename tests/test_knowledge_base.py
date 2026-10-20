import json
import os
import shutil

import pytest
from pydantic import ValidationError

from app.knowledge.models import KnowledgeBase, Price
from app.knowledge.repository import KnowledgeBaseError, KnowledgeBaseRepository
from app.knowledge.search import KnowledgeIndex, stem, tokenize
from tests.conftest import KB_PATH


@pytest.fixture
def kb() -> KnowledgeBase:
    return KnowledgeBaseRepository(KB_PATH).get()


def _minimal_kb(**product_overrides) -> dict:
    product = {
        "id": "a",
        "type": "product",
        "name": "A",
        "category": "C",
        "description": "D",
    }
    product.update(product_overrides)
    return {"company": {"name": "X", "description": "Y"}, "products": [product]}


# ---------- Модели и загрузка ----------


def test_demo_knowledge_base_is_valid(kb):
    assert len(kb.products) >= 5
    for product in kb.products:
        assert product.name and product.description and product.features
        assert product.terms, f"{product.id}: нет условий предоставления"
    assert any(p.price and p.price.amount is None for p in kb.products), "нужен пример без фиксированной цены"


def test_duplicate_ids_are_rejected():
    data = _minimal_kb()
    data["products"].append(dict(data["products"][0]))
    with pytest.raises(ValidationError, match="Повторяющиеся id"):
        KnowledgeBase.model_validate(data)


def test_unknown_related_id_is_rejected():
    with pytest.raises(ValidationError, match="неизвестные id"):
        KnowledgeBase.model_validate(_minimal_kb(related=["missing"]))


def test_price_rendering():
    assert Price(amount=42900, unit="за комплект").render() == "42 900 ₽ за комплект"
    assert Price(amount=None, note="после осмотра").render() == "после осмотра"


def test_knowledge_base_reloads_after_edit(tmp_path):
    path = tmp_path / "kb.json"
    shutil.copy(KB_PATH, path)
    repo = KnowledgeBaseRepository(path)
    assert repo.get().get_product("wifi-module").price.amount == 3500

    data = json.loads(path.read_text(encoding="utf-8"))
    next(p for p in data["products"] if p["id"] == "wifi-module")["price"]["amount"] = 3900
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 5))

    assert repo.get().get_product("wifi-module").price.amount == 3900


def test_broken_edit_keeps_last_valid_version(tmp_path):
    path = tmp_path / "kb.json"
    shutil.copy(KB_PATH, path)
    repo = KnowledgeBaseRepository(path)
    first = repo.get()

    path.write_text("{ broken json", encoding="utf-8")
    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 5))

    assert repo.get() is first
    assert repo.last_error


def test_missing_file_raises(tmp_path):
    with pytest.raises(KnowledgeBaseError):
        KnowledgeBaseRepository(tmp_path / "nope.json").get()


# ---------- Поиск ----------


def test_stemming_matches_word_forms():
    assert stem("установку") == stem("установка") == stem("установить")
    assert stem("кондиционера") == stem("кондиционер")
    assert tokenize("Здравствуйте, сколько стоит?") == []


@pytest.mark.parametrize(
    ("query", "expected_first"),
    [
        ("Сколько стоит монтаж?", "install-standard"),
        ("Хочу почистить кондиционер, появился запах", "service-cleaning"),
        ("Можно оплатить в рассрочку?", "faq-payment"),
        ("Хочу управлять кондиционером со смартфона", "wifi-module"),
        ("Нужен кондиционер в детскую", "breeze-09"),
        ("Кондиционер течёт, капает вода", "faq-repair"),
        ("Кондиционер в спальню 18 м²", "breeze-09"),  # 18 м² — не модель «Бриз 18»
        ("Сколько стоит Бриз 18?", "breeze-18"),
    ],
)
def test_search_finds_relevant_item(kb, query, expected_first):
    hits = KnowledgeIndex(kb).search(query)
    assert hits and hits[0].id == expected_first


def test_search_adds_related_products_as_upsell_candidates(kb):
    hits = KnowledgeIndex(kb).search("Бриз 09", top_k=1)
    assert hits[0].id == "breeze-09"
    related = [h.id for h in hits if h.reason == "related"]
    assert "install-standard" in related


def test_search_returns_nothing_for_small_talk(kb):
    assert KnowledgeIndex(kb).search("Добрый день! Спасибо") == []


def test_search_uses_dialog_context(kb):
    hits = KnowledgeIndex(kb).search("А сколько стоит?", context="Присматриваюсь к Бриз 12")
    assert hits[0].id == "breeze-12"
