from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
import pandas as pd
import numpy as np
from datetime import datetime

app = FastAPI(
    title="Coordinate Transformation API",
    description="API для преобразования координатных данных из Excel",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "message": "Coordinate Transformation API работает",
        "endpoints": {
            "/transform-coordinates/": "POST: загрузка Excel и преобразование координат"
        }
    }

def validate_columns(df: pd.DataFrame, mode: str):
    if mode == "cartesian_to_polar":
        required = ["x", "y"]
    elif mode == "polar_to_cartesian":
        required = ["r", "theta"]
    elif mode == "affine":
        required = ["x", "y"]
    else:
        raise HTTPException(status_code=400, detail=f"Неизвестный режим: {mode}")

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"В файле отсутствуют обязательные столбцы: {', '.join(missing)}"
        )
    return required

def transform_coordinates(
    df: pd.DataFrame,
    mode: str,
    angle_unit: str,
    precision: int,
    affine_params: tuple
) -> pd.DataFrame:
    df_out = df.copy()

    if mode == "cartesian_to_polar":
        x = df["x"].astype(float)
        y = df["y"].astype(float)
        r = np.sqrt(x ** 2 + y ** 2)
        theta = np.arctan2(y, x)
        if angle_unit == "degrees":
            theta = np.degrees(theta)
        df_out["r"] = r.round(precision)
        df_out["theta"] = theta.round(precision)

    elif mode == "polar_to_cartesian":
        r = df["r"].astype(float)
        theta = df["theta"].astype(float)
        if angle_unit == "degrees":
            theta_rad = np.radians(theta)
        else:
            theta_rad = theta
        df_out["x"] = (r * np.cos(theta_rad)).round(precision)
        df_out["y"] = (r * np.sin(theta_rad)).round(precision)

    elif mode == "affine":
        a, b, c, d, e, f = affine_params
        x = df["x"].astype(float)
        y = df["y"].astype(float)
        df_out["x_new"] = (a * x + b * y + c).round(precision)
        df_out["y_new"] = (d * x + e * y + f).round(precision)

    else:
        raise HTTPException(status_code=400, detail=f"Неизвестный режим: {mode}")

    return df_out

def df_to_markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if len(df) > max_rows:
        df = df.head(max_rows)
    try:
        return df.to_markdown(index=False)
    except Exception:
        cols = df.columns
        lines = [
            "| " + " | ".join(cols) + " |",
            "| " + " | ".join(["---"] * len(cols)) + " |"
        ]
        for _, row in df.iterrows():
            lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
        return "\n".join(lines)

def generate_markdown_report(
    df_in: pd.DataFrame,
    df_out: pd.DataFrame,
    mode: str,
    params: dict
) -> str:
    report = "# Отчет о преобразовании координатных данных\n\n"
    report += f"**Дата создания:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    report += "## Параметры преобразования\n\n"
    report += f"- **Режим:** {mode}\n"
    report += f"- **Единицы измерения углов:** {params.get('angle_unit', 'degrees')}\n"
    report += f"- **Точность:** {params.get('precision', 6)} знаков после запятой\n"

    if mode == "affine":
        a, b, c, d, e, f = params["affine_params"]
        report += "- **Аффинное преобразование:**\n"
        report += f"  - x' = {a}·x + {b}·y + {c}\n"
        report += f"  - y' = {d}·x + {e}·y + {f}\n"

    report += "\n## Входные данные\n\n"
    report += f"- **Количество записей:** {len(df_in)}\n"
    report += f"- **Столбцы:** {', '.join(df_in.columns)}\n\n"
    report += "### Первые 10 строк входных данных\n\n"
    report += df_to_markdown_table(df_in.head(10)) + "\n\n"

    report += "## Результаты преобразования\n\n"
    report += f"- **Количество записей:** {len(df_out)}\n"
    new_cols = set(df_out.columns) - set(df_in.columns)
    report += f"- **Новые/изменённые столбцы:** {', '.join(new_cols) if new_cols else 'нет'}\n\n"
    report += "### Первые 20 строк результата\n\n"
    report += df_to_markdown_table(df_out.head(20)) + "\n\n"

    numeric_cols = df_out.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        report += "## Статистика по числовым столбцам результата\n\n"
        stats = df_out[numeric_cols].describe().transpose()
        report += stats.to_markdown() + "\n\n"

    report += "## Выводы\n\n"
    report += f"Преобразование выполнено успешно. Обработано {len(df_out)} записей.\n"
    return report

@app.post("/transform-coordinates/")
async def transform_coordinates_endpoint(
    file: UploadFile = File(...),
    mode: str = Form("cartesian_to_polar"),
    angle_unit: str = Form("degrees"),
    precision: int = Form(6),
    affine_a: float = Form(1.0),
    affine_b: float = Form(0.0),
    affine_c: float = Form(0.0),
    affine_d: float = Form(0.0),
    affine_e: float = Form(1.0),
    affine_f: float = Form(0.0),
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только файлы Excel (.xlsx, .xls)"
        )

    try:
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))

        validate_columns(df, mode)

        affine_params = (affine_a, affine_b, affine_c, affine_d, affine_e, affine_f)
        df_out = transform_coordinates(df, mode, angle_unit, precision, affine_params)

        params = {
            "angle_unit": angle_unit,
            "precision": precision,
            "affine_params": affine_params,
        }
        report = generate_markdown_report(df, df_out, mode, params)

        return {
            "markdown_report": report,
            "processed_data": df_out.head(100).to_dict(orient="records"),
            "filename": f"coordinate_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки файла: {str(e)}")