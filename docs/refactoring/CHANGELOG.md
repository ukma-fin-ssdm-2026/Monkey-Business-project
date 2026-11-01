# Changelog

Усі помітні зміни проєкту фіксуються в цьому файлі. Формат —
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), версії —
[Semantic Versioning](https://semver.org/).

## [0.1.7] - 2026-11-01

### Refactoring:

- Контейнер API запускається від непривілейованого користувача `app`
  замість root; запис дозволено лише в `docs/api`, куди API при старті
  генерує OpenAPI-специфікацію (SonarCloud `docker:S6471`).
  **Техніка:** Run as Non-Root User.
- Сторінці Swagger UI `docs/api/index.html` додано атрибут `lang="uk"`
  (SonarCloud `Web:S5254`).
  **Техніка:** Declare Document Language.

## [0.1.6] - 2026-11-01

### Refactoring:

- Зафіксовано production і development Python-залежності у lock-файлах
  із хешами та підключено `--require-hashes` у CI, деплої документації,
  статичному аналізі й Dockerfile.
  **Техніка:** Lock Dependency Versions.
- Прибрано службовий коментар із generated OpenAPI, який не відтворювався
  генератором і спричиняв помилку перевірки drift.
  **Техніка:** Keep Generated Artifacts Reproducible.

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
- Картку в `CardItem` і закриття модальних вікон по фону в `CardModal` та
  `MentorsPanel` переведено з клікабельних `div` на нативні кнопки
  (SonarCloud `typescript:S6848`).
  **Техніка:** Substitute Algorithm.
- Атрибут `autoFocus` у `NewCardForm` і `StageColumn` замінено функцією
  `focusOnMount` (SonarCloud `typescript:S9379`).
  **Техніка:** Extract Function.
- Дві копії перевірки доступу до картки `_require_card` у `card_links.py` і
  `card_notes.py` замінено спільною функцією `require_card` у
  `src/api/routers/card_access.py`.
  **Техніка:** Extract Function.
- Повторювану обгортку екранів сторінки `InvitationPage.tsx` винесено в
  компонент `InvitationStatusScreen`.
  **Техніка:** Extract Component.

## Використання ШІ

- **Інструменти:** Copilot; Claude — записи `[0.1.7]` і доповнення `[0.1.1]`.
- **Застосування:** оформлення записів про виконані рефакторинги та релізи.
- **Верифікація:** записи звірено з комітами, тегами та перевірками.