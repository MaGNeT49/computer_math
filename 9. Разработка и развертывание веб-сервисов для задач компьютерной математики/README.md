# Практическая работа №10

## Развертывание автоматизированной системы преобразования координатных данных

Проект состоит из двух частей:

- `backend/main.py` — FastAPI;
- `frontend/app.py` — Streamlit;
- `data/generate_test_data.py` — генерация тестового Excel-файла.

## Запуск backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Проверка: открыть `http://127.0.0.1:8000/`.

## Запуск frontend

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

Для другого адреса API:

```bash
BACKEND_URL=https://YOUR-RENDER-SERVICE.onrender.com streamlit run app.py
```

## Render

Создать Web Service из репозитория.

Команда запуска:

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Root Directory: `backend` (если репозиторий содержит эту структуру).

## Streamlit Cloud

Выбрать репозиторий и файл:

```text
frontend/app.py
```

В Secrets/переменных окружения задать:

```text
BACKEND_URL=https://YOUR-RENDER-SERVICE.onrender.com
```

## Тестирование

```bash
python data/generate_test_data.py
```

После этого `test_data.xlsx` можно загрузить во frontend.
