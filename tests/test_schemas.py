"""
Інструмент: Claude
Застосування: Модульний тест схеми створення картки (TP-05 з
docs/validation/test-plan.md; FR-007, US-007).
Верифікація: Запуск pytest; тест падає, якщо прибрати валідатор not_blank у CardBase.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.api.schemas import CardCreate


# TP-05: the equivalence class "whitespace-only string" passes min_length=1,
# so only the not_blank validator stands between it and a stored card.
@pytest.mark.parametrize("company", ["   ", "\t", " \n\t "])
def test_card_create_rejects_whitespace_only_company(company):
    with pytest.raises(ValidationError) as exc_info:
        CardCreate(company=company, position="Python Developer", stage_id=uuid4())

    assert [error["loc"] for error in exc_info.value.errors()] == [("company",)]
