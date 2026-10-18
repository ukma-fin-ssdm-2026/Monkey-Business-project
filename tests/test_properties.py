"""
Тести на основі властивостей (Property-Based Testing) з використанням Hypothesis.
Бонусне завдання: перевірка алгебраїчних властивостей та інваріантів системи
на випадково згенерованих даних різноманітної структури (Unicode, пробіли, емодзі, спецсимволи).
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from src.api.auth import _hash_password, _verify_password
from src.api.validators import validate_vacancy_url


# --------------------------------------------------------------------------- #
# Властивість 1: Round-trip інваріантність криптографічного хешування паролів
# --------------------------------------------------------------------------- #
# Пояснення властивості:
# Для будь-якого згенерованого текстового пароля s функція верифікації _verify_password(s, _hash_password(s))
# завжди повертає True для оригінального рядка і False для будь-якої його модифікації s + '!'.
@settings(deadline=None, max_examples=10, derandomize=True)
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


# Властивість 2: публічний HTTP(S) URL лишається валідним із зовнішніми пробілами.
# Перевіряємо код проєкту, а не властивість вбудованої функції sorted().
@settings(derandomize=True)
@given(
    scheme=st.sampled_from(["http", "https"]),
    label=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=20
    ),
    padding=st.sampled_from(["", " ", "\t\n"]),
)
def test_property_public_url_accepts_surrounding_whitespace(scheme, label, padding):
    url = f"{scheme}://{label}.example.com/jobs/42"

    assert validate_vacancy_url(padding + url + padding) is True
