from io import BytesIO
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

app = FastAPI(
    title="Coordinate Data / Excel Processing API",
    description="API для преобразования координатных данных из Excel "
                "с использованием семипараметрического преобразования Гельмерта",
    version="1.0.0",
)


@app.get("/")
def read_root():
    return {
        "message": "Excel processing API работает",
        "endpoints": {
            "/": "Проверка доступности API",
            "/process-excel/": "Загрузка Excel и получение Markdown-отчета",
        },
    }


def transform_coordinates(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    """
    7-параметрическое преобразование Гельмерта:
    [X']   [dX]         [1    -wz   wy]  [X]
    [Y'] = [dY] + (1+m) [wz    1   -wx] *[Y]
    [Z']   [dZ]         [-wy   wx    1]  [Z]
    """
    dX, dY, dZ = p["dX"], p["dY"], p["dZ"]
    wx, wy, wz = p["wx"], p["wy"], p["wz"]
    m = p["m"]

    X = df["X"].astype(float).values
    Y = df["Y"].astype(float).values
    Z = df["Z"].astype(float).values

    X_new = dX + (1 + m) * (X - wz * Y + wy * Z)
    Y_new = dY + (1 + m) * (wz * X + Y - wx * Z)
    Z_new = dZ + (1 + m) * (-wy * X + wx * Y + Z)

    df_out = df.copy()
    df_out["X'"] = X_new.round(6)
    df_out["Y'"] = Y_new.round(6)
    df_out["Z'"] = Z_new.round(6)
    return df_out


def generate_markdown_report(df: pd.DataFrame) -> str:
    report = "# Отчет по анализу данных\n\n"
    report += f"Дата создания: {datetime.now():%Y-%m-%d %H:%M:%S}\n\n"

    report += "## Общая информация\n\n"
    report += f"- **Количество строк**: {df.shape[0]}\n"
    report += f"- **Количество столбцов**: {df.shape[1]}\n"
    report += f"- **Столбцы**: {', '.join(map(str, df.columns))}\n\n"

    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    if numeric_columns:
        report += "## Статистический анализ\n\n"
        report += "### Числовые данные\n\n"
        stats = df[numeric_columns].describe().transpose()
        report += (
            "| Столбец | Количество | Среднее | Ст. отклонение | "
            "Мин | 25% | 50% | 75% | Макс |\n"
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
        )
        for column, row in stats.iterrows():
            report += (
                f"| {column} | {row['count']:.0f} | {row['mean']:.2f} | "
                f"{row['std']:.2f} | {row['min']:.2f} | {row['25%']:.2f} | "
                f"{row['50%']:.2f} | {row['75%']:.2f} | {row['max']:.2f} |\n"
            )
        report += "\n"

    categorical_columns = df.select_dtypes(
        include=["object", "category"]
    ).columns.tolist()
    if categorical_columns:
        report += "### Категориальные данные\n\n"
        for column in categorical_columns:
            report += f"#### {column}\n\n"
            report += "| Значение | Количество | Процент |\n|---|---:|---:|\n"
            for value, count in df[column].value_counts(dropna=False).head(5).items():
                label = "NaN" if pd.isna(value) else str(value)
                report += f"| {label} | {count} | {count / len(df) * 100:.2f}% |\n"
            report += "\n"

    missing = df.isna().sum()
    report += "## Анализ пропущенных значений\n\n"
    if missing.sum():
        report += "| Столбец | Пропущенные значения | Процент пропущенных |\n"
        report += "|---|---:|---:|\n"
        for column, count in missing.items():
            if count:
                report += f"| {column} | {count} | {count / len(df) * 100:.2f}% |\n"
        report += "\n"
    else:
        report += "Пропущенные значения отсутствуют.\n\n"

    report += "## Выводы\n\n"
    report += (
        f"1. Набор содержит {df.shape[0]} записей и "
        f"{df.shape[1]} характеристик.\n"
    )
    if numeric_columns:
        column = df[numeric_columns].mean().idxmax()
        report += (
            f"2. Среди числовых столбцов наибольшее среднее значение "
            f"имеет «{column}» ({df[column].mean():.2f}).\n"
        )
    if missing.sum():
        column = missing.idxmax()
        report += (
            f"3. Наибольшее число пропусков находится в столбце "
            f"«{column}» ({missing.max()}).\n"
        )
    return report


@app.post("/process-excel/")
async def process_excel(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только файлы Excel (.xlsx, .xls)",
        )

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Файл пустой")

        df = pd.read_excel(BytesIO(contents))
        if df.empty:
            raise HTTPException(status_code=400, detail="Excel-файл не содержит строк")

        transformed = transform_coordinates(df)
        report = generate_markdown_report(transformed)

        output = BytesIO(report.encode("utf-8"))
        output.seek(0)
        report_name = f"report_{datetime.now():%Y%m%d_%H%M%S}.md"

        return StreamingResponse(
            output,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{report_name}"'
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обработки файла: {exc}",
        )
