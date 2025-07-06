import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

# --- CONFIG
USDA_KEY = st.secrets.get("usda_api_key")
PCLOUD_JSON_URL = st.secrets.get("pcloud_prices_url")  # https://link_to_public_json_file
PCLOUD_JSON_WRITE = st.secrets.get("pcloud_prices_write_url")  # POST url if є API (або залиш пустим і тоді ручне оновлення)

# --- LOAD DATA
@st.cache_data
def load_recipes():
    # Структура: id, name, ingredients (json), instructions
    return pd.read_csv("open_recipes_db.csv")

@st.cache_data
def load_prices():
    try:
        r = requests.get(PCLOUD_JSON_URL)
        return r.json()
    except Exception:
        return {}

def save_prices(prices):
    # Зберігаємо файл назад у pCloud (якщо публічний upload/post-URL; якщо нема — показуємо готовий json для ручного копіювання)
    if PCLOUD_JSON_WRITE:
        requests.post(PCLOUD_JSON_WRITE, json=prices)
    else:
        st.warning("Автоматичне збереження недоступне: встав цей JSON вручну у свій pCloud")
        st.code(json.dumps(prices, indent=2))

recipes = load_recipes()
prices = load_prices()

# --- USDA API
@st.cache_data(show_spinner=False)
def get_nutrition(query):
    if not USDA_KEY:
        return {}
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {"api_key": USDA_KEY, "query": query, "pageSize": 1}
    try:
        r = requests.get(url, params=params)
        food = r.json()["foods"][0]
        n = {n["nutrientName"]: n["value"] for n in food["foodNutrients"]}
        return {
            "calories": n.get("Energy", 0),
            "protein": n.get("Protein", 0),
            "fat": n.get("Total lipid (fat)", 0),
            "carbs": n.get("Carbohydrate, by difference", 0)
        }
    except Exception:
        return {}

# --- 1. Пошук рецепту
st.title("🍲 Simple Meal Cost & Nutrition Analyzer")
search_term = st.text_input("Пошук рецепту (англійською):")
search_results = recipes[recipes["name"].str.contains(search_term, case=False)] if search_term else recipes.head(10)

# --- 2. Вибір рецепту
recipe_id = st.selectbox("Вибери рецепт:", search_results["name"].tolist())
recipe = search_results[search_results["name"] == recipe_id].iloc[0] if recipe_id else None

if recipe is not None:
    ingr_list = json.loads(recipe["ingredients"])  # [{'name': ..., 'amount': ..., 'unit': ...}, ...]
    servings = int(recipe.get("servings", 1))
    st.markdown(f"**{recipe['name']}** — {servings} servings")
    st.markdown(recipe["instructions"])

    # --- 3. Таблиця інгредієнтів і ціни
    st.header("Інгредієнти та ціни")
    updated = False
    new_prices = prices.copy()
    cols = st.columns([4, 2, 2, 2, 2, 2])
    cols[0].markdown("**Інгредієнт**")
    cols[1].markdown("**Кількість**")
    cols[2].markdown("**Одиниця**")
    cols[3].markdown("**Ціна/1 кг або пачку (CAD)**")
    cols[4].markdown("**Вага (г/шт/мл)**")
    cols[5].markdown("**Вартість (CAD)**")
    total_cost = 0.0

    ingr_costs, ingr_cals, ingr_prot, ingr_fat, ingr_carb = [], [], [], [], [], []
    for ingr in ingr_list:
        name = ingr["name"]
        amt = float(ingr.get("amount", 0))
        unit = ingr.get("unit", "g")

        ingr_price = float(prices.get(name, {}).get("price", 0))
        ingr_weight = float(prices.get(name, {}).get("weight", 100))
        # Ввід ціни, якщо відсутня
        price_val = cols[3].number_input(f"{name}_price", value=ingr_price, min_value=0.0, key=f"p_{name}")
        weight_val = cols[4].number_input(f"{name}_weight", value=ingr_weight, min_value=1.0, key=f"w_{name}")
        # Користувач зберігає нові ціни
        if price_val != ingr_price or weight_val != ingr_weight:
            new_prices[name] = {"price": price_val, "weight": weight_val}
            updated = True

        # Розрахунок вартості інгредієнта
        if unit in ["g", "ml"]:
            price_per_g = price_val / weight_val if weight_val else 0
            cost = price_per_g * amt
        else:  # наприклад "pcs" — вартість за штуку
            cost = price_val * amt / weight_val if weight_val else 0
        total_cost += cost
        ingr_costs.append(cost)

        # Поживність
        nutr = get_nutrition(name)
        ingr_cals.append(nutr.get("calories", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("calories", 0) * amt)
        ingr_prot.append(nutr.get("protein", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("protein", 0) * amt)
        ingr_fat.append(nutr.get("fat", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("fat", 0) * amt)
        ingr_carb.append(nutr.get("carbs", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("carbs", 0) * amt)

        # Показ рядок
        cols[0].write(name)
        cols[1].write(amt)
        cols[2].write(unit)
        cols[5].write(f"{cost:.2f}")

    # --- Зберегти нові ціни у хмару, якщо треба
    if updated and st.button("💾 Зберегти ціни у pCloud"):
        save_prices(new_prices)
        st.success("Збережено!")

    # --- 4. Аналіз
    st.header("📊 Аналіз страви (на 1 особу)")
    st.write(f"**Вартість:** CAD {total_cost/servings:.2f}")
    st.write(f"**Калорії:** {sum(ingr_cals)/servings:.0f} kcal")
    st.write(f"**Білки:** {sum(ingr_prot)/servings:.1f} г")
    st.write(f"**Жири:** {sum(ingr_fat)/servings:.1f} г")
    st.write(f"**Вуглеводи:** {sum(ingr_carb)/servings:.1f} г")
