"""Функции для решения задачи оптимального объезда точек на дорожной сети (задания 1-6)."""

import osmnx as ox

def make_index_maps(graph):
    """Словари отображения: OSM ID вершины <-> индекс строки/столбца в матрице."""
    node_to_idx = {node: index for index, node in enumerate(graph.nodes)}
    idx_to_node = {index: node for node, index in node_to_idx.items()}
    return node_to_idx, idx_to_node

def load_road_graph(center, radius):
    """Загружает дорожный граф вокруг точки center = (широта, долгота) в радиусе radius метров.

    Возвращает: граф в WGS84 (для карты), граф в UTM (для расчетов в метрах),
    словари node_to_idx и idx_to_node.
    """
    # 1. Загрузка дорожной сети (для автомобиля) из OpenStreetMap
    graph = ox.graph_from_point(center, dist=radius, network_type="drive")
    # Оставляем наибольшую сильно связную компоненту: между любыми двумя ее вершинами
    # существует путь, поэтому расстояния между точками доставки всегда конечны
    graph = ox.truncate.largest_component(graph, strongly=True)
    # 2. Проекция в метрическую систему координат (UTM подбирается автоматически)
    graph_utm = ox.project_graph(graph)
    # 3. Отображения OSM ID <-> индекс в матрице (порядок вершин одинаков в обоих графах)
    node_to_idx, idx_to_node = make_index_maps(graph_utm)
    return graph, graph_utm, node_to_idx, idx_to_node


import re
import numpy as np
from scipy.sparse import csr_matrix

default_speeds = {
    "motorway": 110, "trunk": 90, "primary": 60,
    "secondary": 50, "tertiary": 40, "residential": 30,
    "living_street": 20, "service": 20, "unclassified": 30,
}
default_comfort = {
    "motorway": 0.7, "trunk": 0.8, "primary": 0.85,
    "secondary": 0.9, "tertiary": 1.0, "residential": 1.2,
    "living_street": 1.4, "service": 1.5, "unclassified": 1.3,
}
MPH_TO_KMH = 1.609344

def first_value(value):
    """Атрибуты OSM могут быть списками - берем первый элемент."""
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value

def road_type(highway):
    """Приводит атрибут highway к одному из известных типов дорог."""
    highway = first_value(highway)
    if not isinstance(highway, str):
        return "unclassified"
    highway = highway.replace("_link", "")          # primary_link -> primary
    return highway if highway in default_speeds else "unclassified"

def parse_speed(maxspeed, highway_type):
    """Скорость в км/ч: из maxspeed, а если он отсутствует или некорректен - по типу дороги."""
    value = first_value(maxspeed)
    if value is not None:
        text = str(value).lower()
        found = re.search(r"\d+(?:[.,]\d+)?", text)
        if found:
            speed = float(found.group().replace(",", "."))
            if "mph" in text:
                speed *= MPH_TO_KMH
            if speed > 0:
                return speed
    return float(default_speeds[highway_type])

def edge_weights(data, coefficients):
    """Веса одного ребра: (расстояние, м), (время, с), (комфорт, усл. ед.)."""
    highway_type = road_type(data.get("highway"))
    length = max(float(data.get("length", 0.0)), 1e-6)   # нулевой вес разреженная матрица не отличит от "нет ребра"
    speed_ms = parse_speed(data.get("maxspeed"), highway_type) / 3.6
    return length, length / speed_ms, length * coefficients[highway_type]

def check_coefficients(comfort_coefficients):
    """Полный словарь коэффициентов: пользовательские значения поверх значений по умолчанию."""
    coefficients = dict(default_comfort)
    coefficients.update(comfort_coefficients or {})
    for name, value in coefficients.items():
        if not value > 0:
            raise ValueError(f"Коэффициент для '{name}' должен быть положительным")
    return coefficients

def build_weight_matrices(graph, comfort_coefficients=None):
    """Строит три разреженные CSR-матрицы весов: distance, time, comfort.

    graph - граф NetworkX в проекции UTM. Если между двумя вершинами несколько параллельных
    ребер, для каждого критерия берется самое "дешевое". Возвращает (matrices, node_to_idx, idx_to_node).
    """
    coefficients = check_coefficients(comfort_coefficients)
    node_to_idx, idx_to_node = make_index_maps(graph)
    best = {}                                   # (i, j) -> [расстояние, время, комфорт]
    for start, end, data in graph.edges(data=True):
        key = (node_to_idx[start], node_to_idx[end])
        weights = edge_weights(data, coefficients)
        if key in best:
            best[key] = [min(old, new) for old, new in zip(best[key], weights)]
        else:
            best[key] = list(weights)

    count = len(node_to_idx)
    rows = np.fromiter((key[0] for key in best), dtype=np.int64, count=len(best))
    cols = np.fromiter((key[1] for key in best), dtype=np.int64, count=len(best))
    values = np.array(list(best.values()), dtype=float).reshape(-1, 3)
    matrices = {
        name: csr_matrix((values[:, k], (rows, cols)), shape=(count, count))
        for k, name in enumerate(("distance", "time", "comfort"))
    }
    return matrices, node_to_idx, idx_to_node


from scipy.sparse.csgraph import dijkstra

def point_distances(matrix, point_indices):
    """Матрица кратчайших расстояний N x N между точками доставки.

    Алгоритм Дейкстры запускается ОДИН раз для всех N источников сразу (параметр indices).
    Возвращает (матрица N x N, матрица предшественников N x V).
    """
    point_indices = list(point_indices)
    distances, predecessors = dijkstra(
        csgraph=matrix,
        directed=True,
        indices=point_indices,
        return_predecessors=True,
    )                                            # distances: (N x V)
    between_points = distances[:, point_indices]  # оставляем только столбцы точек доставки -> (N x N)
    if np.isinf(between_points).any():
        raise ValueError("Некоторые точки недостижимы друг из друга по дорожной сети")
    return between_points, predecessors


from itertools import permutations

def route_length(distances, route):
    """Суммарная длина маршрута, заданного последовательностью индексов точек."""
    return sum(distances[a][b] for a, b in zip(route[:-1], route[1:]))

def exact_route(distances, depot=0, max_points=10):
    """Полный перебор всех порядков посещения (для N <= max_points точек, включая депо).

    Возвращает (маршрут вида [depot, ..., depot], его длина).
    """
    d = np.asarray(distances, dtype=float).tolist()      # списки Python работают быстрее индексации NumPy
    n = len(d)
    if n > max_points:
        raise ValueError(f"Полный перебор применим при N <= {max_points}; используйте greedy_route")
    points = [i for i in range(n) if i != depot]
    best_route, best_length = [depot, depot], float("inf")
    if not points:
        return [depot, depot], 0.0
    for order in permutations(points):
        route = [depot, *order, depot]
        length = route_length(d, route)
        if length < best_length:
            best_route, best_length = route, length
    return best_route, best_length

def greedy_route(distances, depot=0):
    """Жадный алгоритм: из текущей точки всегда едем в ближайшую непосещенную. Сложность O(N^2)."""
    d = np.asarray(distances, dtype=float).tolist()
    remaining = set(range(len(d))) - {depot}
    route, current = [depot], depot
    while remaining:
        current = min(remaining, key=lambda point: d[current][point])
        route.append(current)
        remaining.remove(current)
    route.append(depot)                                   # возврат в депо
    return route, route_length(d, route)


NO_PATH = -9999          # значение SciPy в матрице предшественников: "источник" или "пути нет"

def restore_route(order, point_indices, predecessors, idx_to_node):
    """Полный маршрут через все промежуточные вершины графа.

    order - порядок посещения точек (например, [0, 3, 1, 2, 0]);
    point_indices - индексы точек доставки в графе;
    predecessors - матрица предшественников (N x V) из point_distances.
    Возвращает список OSM ID вершин маршрута без дублирования вершин на стыках сегментов.
    """
    route_indices = []
    for a, b in zip(order[:-1], order[1:]):
        start = point_indices[a]                # источник, для которого строилась строка a
        current = point_indices[b]
        segment = [current]
        while current != start:                 # идем от конца сегмента к началу по предшественникам
            current = int(predecessors[a, current])
            if current == NO_PATH:
                raise ValueError(f"Нет пути между точками {a} и {b}")
            segment.append(current)
        segment.reverse()
        route_indices.extend(segment[1:] if route_indices else segment)
    return [idx_to_node[index] for index in route_indices]

def route_metrics(graph, route_nodes, criterion="distance", comfort_coefficients=None):
    """Длина (м) и время (с) вдоль маршрута. Для каждой пары соседних вершин берется ребро,
    которое минимально по выбранному критерию - то же, по которому строился маршрут."""
    coefficients = check_coefficients(comfort_coefficients)
    column = {"distance": 0, "time": 1, "comfort": 2}[criterion]
    total_length = total_time = 0.0
    for start, end in zip(route_nodes[:-1], route_nodes[1:]):
        length, seconds, _ = min(
            (edge_weights(data, coefficients) for data in graph[start][end].values()),
            key=lambda weights: weights[column],
        )
        total_length += length
        total_time += seconds
    return total_length, total_time


def recalculate_comfort(graph, coefficients):
    """Пересчитывает матрицу комфорта с пользовательскими коэффициентами типов дорог.

    graph - граф NetworkX в проекции UTM, coefficients - словарь {тип дороги: коэффициент}.
    Типы, которых нет в словаре, берутся из default_comfort. Возвращает CSR-матрицу.
    """
    matrices, node_to_idx, idx_to_node = build_weight_matrices(graph, coefficients)
    return matrices["comfort"]
