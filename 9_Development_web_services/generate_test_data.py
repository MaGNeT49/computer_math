import pandas as pd
import numpy as np

np.random.seed(42)
n = 100

# Декартовы координаты
x = np.random.uniform(-1000, 1000, n).round(3)
y = np.random.uniform(-1000, 1000, n).round(3)
df_cart = pd.DataFrame({"x": x, "y": y})
df_cart.to_excel("test_cartesian.xlsx", index=False)

# Полярные координаты
r = np.sqrt(x ** 2 + y ** 2).round(3)
theta = np.degrees(np.arctan2(y, x)).round(6)
df_polar = pd.DataFrame({"r": r, "theta": theta})
df_polar.to_excel("test_polar.xlsx", index=False)

print("Созданы файлы: test_cartesian.xlsx, test_polar.xlsx")