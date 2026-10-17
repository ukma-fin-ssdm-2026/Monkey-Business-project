"""
Тести на основі властивостей (Property-Based Testing) з використанням Hypothesis.
Бонусне завдання: перевірка алгебраїчних властивостей та інваріантів системи
на випадково згенерованих даних різноманітної структури (Unicode, пробіли, емодзі, спецсимволи).
"""

from __future__ import annotations

from uuid import uuid4

from hypothesis import given, settings, strategies as st

from src.api.auth import _hash_password, _verify_password
from src.api.domain import Stage


# --------------------------------------------------------------------------- #
# Властивість 1: Round-trip інваріантність криптографічного хешування паролів
# --------------------------------------------------------------------------- #
# Пояснення властивості:
# Для будь-якого згенерованого текстового пароля s функція верифікації _verify_password(s, _hash_password(s))
# завжди повертає True для оригінального рядка і False для будь-якої його модифікації s + '!'.
@settings(deadline=None, max_examples=10)
@given(
    st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=1,
        max_size=100,
    )
)
def test_property_password_hash_verification_roundtrip(password: str):
    hashed = _hash_password(password)

    # Інваріант 1: Оригінальний пароль завжди успішно проходить верифікацію
    assert _verify_password(password, hashed) is True

    # Інваріант 2: Змінений пароль завжди відхиляється
    altered = password + "!"
    assert _verify_password(altered, hashed) is False


# --------------------------------------------------------------------------- #
# Властивість 2: Інваріант сортування етапів за order_index
# --------------------------------------------------------------------------- #
# Пояснення властивості:
# Для будь-якого довільного списку етапів із випадковими цілими числами order_index,
# сортування за order_index гарантує монотонію: кожен наступний елемент має order_index >= попереднього.
@given(
    st.lists(
        st.integers(min_value=-1000, max_value=1000),
        min_size=1,
        max_size=30,
    )
)
def test_property_stages_ordering_monotonicity(order_indices: list[int]):
    board_id = uuid4()
    stages = [
        Stage(board_id=board_id, name=f"Stage_{i}", order_index=idx)
        for i, idx in enumerate(order_indices)
    ]

    sorted_stages = sorted(stages, key=lambda s: s.order_index)

    # Перевірка властивості монотонності
    for i in range(len(sorted_stages) - 1):
        assert sorted_stages[i].order_index <= sorted_stages[i + 1].order_index
