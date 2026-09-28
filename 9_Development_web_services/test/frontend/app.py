import streamlit as st
import pandas as pd
import requests
from urllib.parse import urljoin

st.set_page_config(
    page_title="Coordinate Transformer",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# URL бэкенда. Замените на свой после развёртывания на render.com
BACKEND_URL = st.secrets.get("BACKEND_URL", "https://your-backend.onrender.com")

def check_api_status():
    try:
        r = requests.get(BACKEND_URL, timeout=10)
        return r.status_code == 200
    except requests.RequestException:
        return False

def send_transform(file, params):
    url = urljoin(BACKEND_URL, "/transform-coordinates/")
    files = {"file": file}
    try:
        r = requests.post(url, files=files, data=params)
        if r.status_code == 200:
            return r.json()
        else:
            st.error(f"Ошибка API: {r.status_code} — {r.text}")
            return None
    except requests.RequestException as e:
        st.error(f"Ошибка соединения с API: {e}")
        return None

def main():
    st.title("🌐 Преобразование координатных данных")
    st.markdown("""
    Загрузите Excel-файл с координатами, выберите режим преобразования
    и получите отчёт в формате Markdown.
    """)

    if not check_api_status():
        st.error("⚠️ Бэкенд недоступен. Проверьте URL или попробуйте позже.")
        return

    with st.sidebar:
        st.header("Параметры преобразования")
        mode = st.selectbox(
            "Режим",
            ["cartesian_to_polar", "polar_to_cartesian", "affine"],
            format_func=lambda x: {
                "cartesian_to_polar": "Декартовы → Полярные",
                "polar_to_cartesian": "Полярные → Декартовы",
                "affine": "Аффинное преобразование"
            }[x]
        )
        angle_unit = st.radio("Единицы углов", ["degrees", "radians"], index=0)
        precision = st.slider("Точность (знаков после запятой)", 1, 12, 6)

        affine_params = {}
        if mode == "affine":
            st.subheader("Параметры аффинного преобразования")
            a = st.number_input("a", value=1.0)
            b = st.number_input("b", value=0.0)
            c = st.number_input("c", value=0.0)
            d = st.number_input("d", value=0.0)
            e = st.number_input("e", value=1.0)
            f = st.number_input("f", value=0.0)
            affine_params = {
                "affine_a": a, "affine_b": b, "affine_c": c,
                "affine_d": d, "affine_e": e, "affine_f": f
            }

    uploaded_file = st.file_uploader("Выберите Excel-файл", type=["xlsx", "xls"])

    if uploaded_file is not None:
        try:
            df_preview = pd.read_excel(uploaded_file)
            st.subheader("Предварительный просмотр данных")
            st.dataframe(df_preview.head(10))
            uploaded_file.seek(0)
        except Exception as e:
            st.error(f"Ошибка чтения файла: {e}")
            return

        if st.button("Выполнить преобразование", type="primary"):
            params = {
                "mode": mode,
                "angle_unit": angle_unit,
                "precision": precision,
                **affine_params
            }
            with st.spinner("Отправка файла на сервер..."):
                result = send_transform(uploaded_file, params)

            if result:
                st.success("Преобразование выполнено успешно!")
                report = result["markdown_report"]

                st.subheader("Отчёт")
                st.markdown(report)

                st.download_button(
                    label="Скачать отчёт (Markdown)",
                    data=report,
                    file_name=result.get("filename", "report.md"),
                    mime="text/markdown"
                )

                if "processed_data" in result:
                    st.subheader("Обработанные данные (первые 100 строк)")
                    st.dataframe(pd.DataFrame(result["processed_data"]))
    else:
        st.info("Загрузите Excel-файл, чтобы начать.")

if __name__ == "__main__":
    main()