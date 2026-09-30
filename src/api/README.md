# Запуск API
 
```bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload --port 8000
```
 
- Swagger UI: http://localhost:8000/docs
- Специфікація OpenAPI (JSON, генерується автоматично з коду): http://localhost:8000/openapi.json

Дані зберігаються в пам'яті (`store.py`) — це заглушка для демонстрації
Code-First підходу.
 