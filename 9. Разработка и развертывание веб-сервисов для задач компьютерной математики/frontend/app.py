import io
import os
from urllib.parse import urljoin

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Анализатор Excel",
    layout="wide",
)

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "https://excel-to-markdown-api.onrender.com",
).rstrip("/")


def check_api_status() -> bool:
    try:
        response = requests.get(BACKEND_URL, timeout=10)
        return response.ok
    except requests.RequestException:
        return False


def process_excel(uploaded_file):
    url = urljoin(BACKEND_URL + "/", "process-excel/")
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }
    try:
        response = requests.post(url, files=files, timeout=120)
        if response.ok:
            return response.content.decode("utf-8")
        st.error(f"Ошибка API: {response.status_code}: {response.text}")
    except requests.RequestException as exc:
        st.error(f"Ошибка соединения с API: {exc}")
    return None


def main():
    st.title("Анализатор Excel-файлов")
    st.write(
        "Загрузите Excel-файл. Бэкенд обработает данные и вернет "
        "отчет в формате Markdown."
    )

    with st.sidebar:
        st.subheader("Параметры")
        st.code(BACKEND_URL)
        if check_api_status():
            st.success("API доступен")
        else:
            st.error("API недоступен")

    uploaded_file = st.file_uploader(
        "Выберите Excel-файл",
        type=["xlsx", "xls"],
    )

    if uploaded_file is None:
        return

    try:
        df = pd.read_excel(io.BytesIO(uploaded_file.getvalue()))

        st.subheader("Предварительный просмотр")
        st.dataframe(df.head(10), use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Строки", df.shape[0])
        c2.metric("Столбцы", df.shape[1])
        c3.metric("Пропуски", int(df.isna().sum().sum()))

        numeric = df.select_dtypes(include="number").columns.tolist()
        if numeric:
            st.subheader("Визуализация числовых данных")
            selected = st.selectbox("Числовой столбец", numeric)
            st.line_chart(df[selected])

        if st.button("Анализировать", type="primary"):
            with st.spinner("Обрабатываем файл..."):
                report = process_excel(uploaded_file)

            if report:
                st.success("Отчет успешно создан")
                st.subheader("Markdown-отчет")
                st.markdown(report)
                st.download_button(
                    "Скачать report.md",
                    data=report,
                    file_name="report.md",
                    mime="text/markdown",
                )
    except Exception as exc:
        st.error(f"Ошибка чтения Excel-файла: {exc}")


if __name__ == "__main__":
    main()
