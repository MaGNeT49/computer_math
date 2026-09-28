import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

np.random.seed(42)
random.seed(42)

num_rows = 100
data = {
    "Продажи": np.random.normal(1000, 200, num_rows).round(2),
    "Маржа": np.random.uniform(0.05, 0.25, num_rows).round(4),
    "Количество": np.random.randint(1, 100, num_rows),
}
data["Цена"] = (data["Продажи"] / data["Количество"]).round(2)

start_date = datetime(2023, 1, 1)
data["Дата"] = [
    start_date + timedelta(days=random.randint(0, 365))
    for _ in range(num_rows)
]
data["Категория"] = [
    random.choice(["Электроника", "Одежда", "Книги", "Товары для дома", "Спорт", "Продукты"])
    for _ in range(num_rows)
]
data["ТипКлиента"] = [
    random.choice(["Розница", "Опт", "Онлайн"]) for _ in range(num_rows)
]
data["Регион"] = [
    random.choice(["Север", "Юг", "Восток", "Запад", "Центр"])
    for _ in range(num_rows)
]
data["Рейтинг"] = np.random.uniform(1, 5, num_rows).round(1)
for idx in np.random.choice(num_rows, size=10, replace=False):
    data["Рейтинг"][idx] = np.nan

data["СпособОплаты"] = [
    random.choice(["Карта", "Наличные", "Банковский перевод", "PayPal"])
    for _ in range(num_rows)
]
for idx in np.random.choice(num_rows, size=15, replace=False):
    data["СпособОплаты"][idx] = None

data["Возврат"] = [random.choice([0, 1]) for _ in range(num_rows)]
data["СрочныйЗаказ"] = [random.choice([0, 1]) for _ in range(num_rows)]

pd.DataFrame(data).to_excel("test_data.xlsx", index=False)
print("Создан test_data.xlsx")
