## [0.1.5] - 2026-11-01

### Refactoring:

- Оновлено `mutmut` з недоступної для binary-only інсталяції версії `2.5.1`
  до `3.8.1`, яка має Python wheel.
  **Техніка:** Upgrade Dependency Version.

## [0.1.4] - 2026-10-31

### Refactoring:

- У CI, деплої документації та Dockerfile додано
  `--only-binary=:all:` для встановлення Python-залежностей, щоб заборонити
  збірку пакетів із вихідного коду та виконання setup-скриптів.
  **Техніка:** Constrain Build Dependencies.

## [0.1.3] - 2026-10-31

### Refactoring:

- Закріплено GitHub Action `peaceiris/actions-gh-pages` на повному SHA
  `84c30a85c19949d7eee79c4ff27748b70285e453`.
  **Техніка:** Pin Dependency Version.

## [0.1.2] - 2026-10-31

### Refactoring:

- Видалено непотрібний параметр `scope="function"` із залежності
  репозиторіїв у `src/api/db.py`.
  **Техніка:** Simplify Method Call.

## [0.1.1] - 2026-10-31

### Refactoring:

- Прибрано fallback-пароль PostgreSQL із Docker Compose та залишено
  обов'язкову змінну середовища `POSTGRES_PASSWORD`.
  **Техніка:** Externalize Configuration.
- Додано регресійні перевірки, що секрет не зберігається в Compose або CI.
  **Техніка:** Characterization Test.