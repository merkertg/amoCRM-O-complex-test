"""Схема базы знаний. Файл data/knowledge_base.json валидируется по этим моделям."""

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ID_PATTERN = r"^[a-z0-9][a-z0-9\-]*$"


def format_amount(amount: float) -> str:
    """42900 -> «42 900»."""
    if float(amount).is_integer():
        return f"{int(amount):,}".replace(",", " ")
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


class Price(BaseModel):
    amount: float | None = Field(default=None, ge=0, description="null — цена не фиксирована")
    currency: str = "₽"
    unit: str | None = Field(default=None, description="Например: «за выезд», «за метр»")
    note: str | None = None

    def render(self) -> str:
        if self.amount is None:
            return self.note or "не указана — уточнить у менеджера"
        text = f"{format_amount(self.amount)} {self.currency}"
        if self.unit:
            text += f" {self.unit}"
        if self.note:
            text += f" ({self.note})"
        return text


class Product(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    type: Literal["product", "service"]
    name: str
    category: str
    description: str
    features: list[str] = Field(default_factory=list)
    price: Price | None = None
    terms: list[str] = Field(default_factory=list, description="Условия предоставления")
    related: list[str] = Field(default_factory=list, description="ID связанных позиций")
    upsell_scenarios: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list, description="Синонимы для поиска")

    @property
    def type_label(self) -> str:
        return "товар" if self.type == "product" else "услуга"


class FAQEntry(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    topic: str
    answer: str
    keywords: list[str] = Field(default_factory=list)


class Company(BaseModel):
    name: str
    description: str
    working_hours: str | None = None


class KnowledgeBase(BaseModel):
    company: Company
    products: list[Product]
    faq: list[FAQEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_ids(self) -> "KnowledgeBase":
        ids = [p.id for p in self.products] + [f.id for f in self.faq]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"Повторяющиеся id: {sorted(duplicates)}")
        product_ids = {p.id for p in self.products}
        for product in self.products:
            unknown = set(product.related) - product_ids
            if unknown:
                raise ValueError(f"{product.id}: неизвестные id в related: {sorted(unknown)}")
        return self

    def get_product(self, product_id: str | None) -> Product | None:
        if not product_id:
            return None
        return next((p for p in self.products if p.id == product_id), None)

    def get_faq(self, faq_id: str) -> FAQEntry | None:
        return next((f for f in self.faq if f.id == faq_id), None)

    def find_product_by_name(self, name: str | None) -> Product | None:
        """Ищет позицию по названию: точное совпадение или однозначное частичное."""
        needle = _normalize_name(name or "")
        if not needle:
            return None
        names = {p.id: _normalize_name(p.name) for p in self.products}
        for product in self.products:
            if names[product.id] == needle or names[product.id] in needle:
                return product
        partial = [p for p in self.products if needle in names[p.id]]
        return partial[0] if len(partial) == 1 else None


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[«»\"'“”„]", "", value)).strip().lower()
