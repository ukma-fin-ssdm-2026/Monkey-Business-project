# Інструмент: Claude.
# Застосування: регресійна перевірка зауваження SonarCloud Web:S5254 для сторінки Swagger UI.
# Верифікація: тест падав до додавання атрибута lang і проходить після.

import re
from pathlib import Path

INDEX = Path(__file__).parents[1] / "docs" / "api" / "index.html"


def test_api_docs_page_declares_language():
    assert re.search(r'<html\b[^>]*\blang="[a-z]{2}', INDEX.read_text())
