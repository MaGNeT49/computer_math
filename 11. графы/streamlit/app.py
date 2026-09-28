'''Веб-приложение «Оптимальный объезд точек» (Streamlit).

Запуск:  streamlit run app.py
'''
from __future__ import annotations

import time
from math import asin, cos, radians, sin, sqrt

import folium
import osmnx as ox
import streamlit as st
from geopy.geocoders import Nominatim
from pyproj import Transformer
from streamlit_folium import st_folium

from graph_utils import (
    default_comfort, build_weight_matrices, exact_route, greedy_route, load_road_graph,
    point_distances, restore_route, route_metrics,
)

APP_TITLE = "Оптимальный объезд точек"
DEFAULT_CENTER = [55.751244, 37.618423]
SEARCH_LIMIT = 5
CRITERIA = {"distance": "Расстояние", "time": "Время", "comfort": "Комфорт"}
ROAD_TYPES = {
    "motorway": "Автомагистраль", "trunk": "Скоростная дорога", "primary": "Главная дорога",
    "secondary": "Второстепенная дорога", "tertiary": "Местная дорога",
    "residential": "Жилая улица", "living_street": "Жилая зона",
    "service": "Служебная дорога", "unclassified": "Неклассифицированная",
}


def init_state():
    st.session_state.setdefault("search_results", [])
    st.session_state.setdefault("points", [])            # первая точка - депо
    st.session_state.setdefault("route", None)
    st.session_state.setdefault("coefficients", dict(default_comfort))


def reset_route():
    st.session_state.route = None


@st.cache_resource
def get_geolocator():
    return Nominatim(user_agent="computer_math_route_planner")


@st.cache_data(ttl=3600, show_spinner=False)
def search_address(query):
    time.sleep(1.1)                                       # ограничение Nominatim: не чаще 1 запроса в секунду
    places = get_geolocator().geocode(query, exactly_one=False, limit=SEARCH_LIMIT,
                                      language="ru", timeout=10) or []
    return [{"address": p.address, "lat": p.latitude, "lon": p.longitude} for p in places]


def distance_between(lat1, lon1, lat2, lon2):
    """Расстояние по сфере (формула гаверсинуса), метры."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    value = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 12742000 * asin(sqrt(value))


@st.cache_resource(show_spinner=False)
def cached_graph(lat, lon, radius):
    return load_road_graph((lat, lon), radius)


def build_route():
    points = st.session_state.points
    depot = points[0]
    radius = max(distance_between(depot["lat"], depot["lon"], p["lat"], p["lon"]) for p in points)
    radius = int((radius + 1500) // 100 * 100 + 100)      # запас + округление, чтобы граф чаще брался из кэша
    graph, graph_utm, node_to_idx, idx_to_node = cached_graph(round(depot["lat"], 5), round(depot["lon"], 5), radius)

    criterion = st.session_state.criterion
    coefficients = st.session_state.coefficients
    matrices, node_to_idx, idx_to_node = build_weight_matrices(graph_utm, coefficients)

    # Привязка точек к ближайшим вершинам графа (в проекции граф хранит координаты в метрах)
    transformer = Transformer.from_crs("EPSG:4326", graph_utm.graph["crs"], always_xy=True)
    point_indices = []
    for p in points:
        x, y = transformer.transform(p["lon"], p["lat"])
        point_indices.append(node_to_idx[ox.distance.nearest_nodes(graph_utm, x, y)])

    distances, predecessors = point_distances(matrices[criterion], point_indices)
    order, score = exact_route(distances) if len(points) <= 10 else greedy_route(distances)
    nodes = restore_route(order, point_indices, predecessors, idx_to_node)
    length_m, seconds = route_metrics(graph_utm, nodes, criterion, coefficients)
    st.session_state.route = {"graph": graph, "nodes": nodes, "order": order,
                              "length": length_m, "time": seconds}


def create_map(points, route):
    center = [points[0]["lat"], points[0]["lon"]] if points else DEFAULT_CENTER
    fmap = folium.Map(location=center, zoom_start=12, control_scale=True)
    for index, p in enumerate(points):
        title = ("Депо: " if index == 0 else f"Точка {index}: ") + p["address"]
        folium.Marker([p["lat"], p["lon"]], tooltip=title,
                      icon=folium.Icon(color="red" if index == 0 else "blue")).add_to(fmap)
    if route is not None:
        line = [[route["graph"].nodes[n]["y"], route["graph"].nodes[n]["x"]] for n in route["nodes"]]
        folium.PolyLine(line, color="green", weight=5, tooltip="Маршрут").add_to(fmap)
    return fmap


def sidebar():
    with st.sidebar:
        # --- Блок поиска адреса ---
        st.header("Поиск адреса")
        query = st.text_input("Введите адрес")
        if st.button("Найти") and query.strip():
            try:
                st.session_state.search_results = search_address(query.strip())
                if not st.session_state.search_results:
                    st.warning("Ничего не найдено")
            except Exception as error:                    # сетевые ошибки геокодера
                st.error(f"Ошибка поиска адреса: {error}")
        for i, place in enumerate(st.session_state.search_results):
            st.caption(place["address"])
            if st.button("Добавить", key=f"add_{i}"):
                st.session_state.points.append(dict(place))
                st.session_state.search_results = []
                reset_route()
                st.rerun()

        # --- Блок списка точек ---
        st.header("Точки маршрута")
        if not st.session_state.points:
            st.caption("Добавьте минимум две точки; первая точка - депо")
        for i, p in enumerate(st.session_state.points):
            name_col, button_col = st.columns([4, 1])
            name_col.write(f"{'Депо' if i == 0 else i}. {p['address']}")
            if button_col.button("✕", key=f"remove_{i}", help="Удалить точку"):
                st.session_state.points.pop(i)
                reset_route()
                st.rerun()
        if st.button("Очистить всё"):
            st.session_state.points = []
            reset_route()
            st.rerun()

        # --- Блок настройки маршрута ---
        st.header("Маршрут")
        st.radio("Критерий оптимизации", list(CRITERIA), format_func=CRITERIA.get,
                 key="criterion", on_change=reset_route)

        # --- Блок настройки коэффициентов (только для критерия «комфорт») ---
        if st.session_state.criterion == "comfort":
            with st.expander("Коэффициенты комфорта", expanded=True):
                new_values = {}
                for road, title in ROAD_TYPES.items():
                    new_values[road] = st.number_input(
                        f"{road} ({title})", min_value=0.1, max_value=5.0, step=0.1,
                        value=float(st.session_state.coefficients[road]), key=f"coef_{road}")
                if st.button("Применить коэффициенты"):
                    st.session_state.coefficients = new_values
                    reset_route()
                    st.success("Коэффициенты применены")

        if st.button("Построить маршрут", type="primary"):
            if len(st.session_state.points) < 2:
                st.warning("Нужно минимум две точки")
            else:
                with st.spinner("Загружаю дорожную сеть и строю маршрут..."):
                    try:
                        build_route()
                    except Exception as error:
                        st.error(f"Не удалось построить маршрут: {error}")


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()
    st.title(APP_TITLE)
    sidebar()

    route = st.session_state.route
    st_folium(create_map(st.session_state.points, route), height=560,
              use_container_width=True, returned_objects=[])
    if route is not None:
        col_km, col_min = st.columns(2)
        col_km.metric("Длина маршрута", f"{route['length'] / 1000:.2f} км")
        col_min.metric("Время в пути (примерно)", f"{route['time'] / 60:.0f} мин")
        st.subheader("Порядок посещения")
        for step, index in enumerate(route["order"][:-1]):
            st.write(f"{step + 1}. {st.session_state.points[index]['address']}")
        st.write(f"{len(route['order'])}. Возврат в депо")


if __name__ == "__main__":
    main()
