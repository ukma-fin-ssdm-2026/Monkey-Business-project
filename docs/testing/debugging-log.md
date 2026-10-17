# Журнал налагодження (Debugging Log)

Цей документ фіксує процес систематичного налагодження дефекту, виявленого та виправленого під час активності **Test-a-Thon** (Лабораторна робота №6).

---

## 1. Загальні відомості про помилку
- **Компонент:** Канбан-етапи дошки (`src/api/routers/stages.py`, FR-024).
- **Тип помилки:** Логічна помилка валідації бізнес-правил цілісності даних.
- **Критичність:** High (порушення цілісності зв'язків між етапами та картками вакансій).

---

## 2. Систематичний аналіз помилки

### Симптом (Symptom)
При спробі видалити етап через виклик `DELETE /boards/{board_id}/stages/{stage_id}` система дозволяла безповоротно видалити етап, навіть якщо на ньому знаходилися активні картки вакансій кандидата. У результаті пов'язані картки залишалися з посиланням на неіснуючий `stage_id` ("orphaned records"), що призводило до збоїв рендерингу Канбан-дошки у frontend-додатку.

### Причина (Root Cause)
У функції `delete_stage` роутера `src/api/routers/stages.py` було пропущено виклик перевірки наявності прив'язаних карток або умова була проігнорована:
```python
# Дефектний стан: етап видалявся без попередньої перевірки наповненості
def delete_stage(board_id: UUID, stage_id: UUID, user: CandidateOrAdmin, repos: Repos):
    _require_board(repos, board_id, user, write=True)
    _require_stage(repos, board_id, stage_id)
    # Відсутня перевірка repos.stages.has_cards(stage_id)
    repos.stages.delete(stage_id)
```
Це порушувало вимогу FR-024 та специфікацію API, згідно з якою спроба видалення непустого етапу повинна повертати статус-код `409 Conflict`.

### Виправлення (Fix)
Перед викликом `repos.stages.delete(stage_id)` додано валідацію через репозиторій. Якщо на етапі є бодай одна картка, викидається доменний виняток `ConflictError`:
```python
# Виправлений стан:
def delete_stage(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    stage_id: UUID = Path(..., description="Ідентифікатор етапу"),
    user: CandidateOrAdmin = None,
    repos: Repos = None,
) -> None:
    _require_board(repos, board_id, user, write=True)
    _require_stage(repos, board_id, stage_id)
    if repos.stages.has_cards(stage_id):
        raise ConflictError("Неможливо видалити етап, у якому є картки")
    repos.stages.delete(stage_id)
```

---

## 3. Регресійне тестування

Для запобігання повторній появі помилки до набору тестів додано спеціалізований регресійний тест у `tests/test_stages.py`:

```python
def test_delete_stage_raises_conflict_when_stage_has_cards(repos, board, owner):
    # Arrange: Створюємо етап і позначаємо його як такий, що містить картки
    stage = repos.stages.add(Stage(board_id=board.id, name="Етап із картками", order_index=0))
    repos.stages.stages_with_cards.add(stage.id)

    # Act & Assert: Очікуємо ConflictError (409 Conflict)
    with pytest.raises(ConflictError) as exc_info:
        stages_router.delete_stage(
            board_id=board.id, stage_id=stage.id, user=owner, repos=repos
        )
    assert "Неможливо видалити етап, у якому є картки" in str(exc_info.value)
    
    # Перевірка: етап залишився у репозиторії
    assert repos.stages.get(stage.id) is not None
```

---

## 4. Засвоєний урок (Lessons Learned)
1. **Захист на двох рівнях:** Логічні обмеження цілісності мають обов'язково контролюватися як на рівні додатку (FastAPI роутер / бізнес-шар), так і на рівні бази даних (`ON DELETE RESTRICT` у foreign key міграції PostgreSQL).
2. **Пріоритет негативних тестів:** Написання модульних тестів на успішний шлях (Happy Path) не гарантує стабільності системи; тестування крайових конфліктних випадків (409, 403, 404) виявляє до 80% критичних логічних дефектів до потрапляння коду в продакшн.
