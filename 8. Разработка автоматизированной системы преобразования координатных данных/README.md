# Автоматизированная система преобразования координатных данных

## Описание
Клиент-серверная система:
- **Бэкенд (FastAPI)** принимает Excel-файл с координатами X, Y, Z,
  выполняет семипараметрическое преобразование Гельмерта
  и возвращает Markdown-отчёт.
- **Фронтенд (Streamlit)** предоставляет интерфейс загрузки файла
  и скачивания отчёта.

## Технологии
Python 3.11, FastAPI, Uvicorn, Streamlit, Pandas, NumPy, OpenPyXL,
Render.com, Streamlit Cloud.

## Локальный запуск
```bash
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt

# терминал 1
cd backend && uvicorn main:app --reload

# терминал 2
cd frontend && streamlit run app.py