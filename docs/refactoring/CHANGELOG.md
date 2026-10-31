## [0.1.1] - 2026-10-31

### Refactoring:

- Прибрано fallback-пароль PostgreSQL із Docker Compose та залишено
  обов'язкову змінну середовища `POSTGRES_PASSWORD`.
  **Техніка:** Externalize Configuration.
- Додано регресійні перевірки, що секрет не зберігається в Compose або CI.
  **Техніка:** Characterization Test.