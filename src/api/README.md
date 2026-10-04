# Запуск API
 
```bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload --port 3000
python -m src.api.main   # згенерувати docs/api/openapi-generated.yaml без запуску сервера
```
 
- Swagger UI: http://localhost:3000/api-docs
- Специфікація OpenAPI (JSON, генерується автоматично з коду): http://localhost:3000/openapi.json
- Специфікація OpenAPI (YAML): [`docs/api/openapi-generated.yaml`](../../docs/api/openapi-generated.yaml) — оновлюється при кожному запуску сервера

Дані зберігаються в пам'яті (`store.py`) — це заглушка для демонстрації
Code-First підходу.
