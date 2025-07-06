import streamlit as st
import sqlite3
import json
import pandas as pd
import requests
from datetime import datetime

DB_PATH = "meals_db.sqlite"
USDA_KEY = st.secrets.get("usda_api_key", "")

# ---- ІНІЦІАЛІЗАЦІЯ БД ----
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    servings INTEGER,
                    ingredients TEXT,     -- JSON [{'name':..,'amount':..,'unit':..}]
                    instructions TEXT
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS ingredient_prices (
                    name TEXT PRIMARY KEY,
                    price REAL,
                    weight REAL
                )""")
    conn.commit()
    conn.close()
init_db()

def get_conn():
    return sqlite3.connect(DB_PATH)

# ---- РОБОТА З РЕЦЕПТАМИ ----
def get_all_recipes():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM recipes", conn)
    conn.close()
    return df

def get_recipe_by_name(name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM recipes WHERE name=?", (name,))
    row = c.fetchone()
    conn.close()
    return row

def add_recipe(name, servings, ingredients, instructions):
    conn = get_conn()
    conn.execute(
        "INSERT INTO recipes (name, servings, ingredients, instructions) VALUES (?, ?, ?, ?)",
        (name, servings, json.dumps(ingredients), instructions))
    conn.commit()
    conn.close()

# ---- РОБОТА З ІНГРЕДІЄНТАМИ ----
def get_prices():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM ingredient_prices", conn, index_col="name")
    conn.close()
    return df.to_dict(orient="index")

def save_price(name, price, weight):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO ingredient_prices (name, price, weight) VALUES (?, ?, ?)",
        (name, price, weight)
    )
    conn.commit()
    conn.close()

# ---- USDA NUTRITION ----
@st.cache_data(show_spinner=False)
def get_nutrition(query):
    if not USDA_KEY:
        return {}
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {"api_key": USDA_KEY, "query": query, "pageSize": 1}
    try:
        r = requests.get(url, params=params)
        food = r.json()["foods"][0]
        n = {n["nutrientName"]: n["value"] for n in food.get("foodNutrients", [])}
        return {
            "calories": n.get("Energy", 0),
            "protein": n.get("Protein", 0),
            "fat": n.get("Total lipid (fat)", 0),
            "carbs": n.get("Carbohydrate, by difference", 0)
        }
    except Exception:
        return {}

# ---- UI ----

st.title("🍲 Meal Cost & Nutrition Analyzer (SQLite Edition)")
mode = st.sidebar.radio("Режим", ["Вибір рецепту", "Додати рецепт", "Редагувати ціни", "Завантажити базу"])

# --- ВИБІР/АНАЛІЗ РЕЦЕПТУ ---
if mode == "Вибір рецепту":
    df_recipes = get_all_recipes()
    if df_recipes.empty:
        st.info("Додайте хоча б один рецепт.")
    else:
        search = st.text_input("Пошук рецепту:")
        if search:
            filtered = df_recipes[df_recipes["name"].str.contains(search, case=False, na=False)]
        else:
            filtered = df_recipes
        recipe_name = st.selectbox("Оберіть рецепт:", filtered["name"].tolist())
        if recipe_name:
            row = df_recipes[df_recipes["name"] == recipe_name].iloc[0]
            servings = int(row["servings"])
            ingr_list = json.loads(row["ingredients"])
            st.markdown(f"**{row['name']}** — {servings} servings")
            st.markdown(row["instructions"])
            st.subheader("Інгредієнти та ціни")
            prices = get_prices()
            updated = False
            total_cost = 0.0
            ingr_cals, ingr_prot, ingr_fat, ingr_carb = [], [], [], []

            for ingr in ingr_list:
                name = ingr["name"]
                amt = float(ingr.get("amount", 0))
                unit = ingr.get("unit", "g")
                ingr_price = float(prices.get(name, {}).get("price", 0))
                ingr_weight = float(prices.get(name, {}).get("weight", 100))
                cols = st.columns([4, 2, 2, 2, 2, 2])
                cols[0].write(name)
                cols[1].write(amt)
                cols[2].write(unit)
                price_val = cols[3].number_input(f"{name}_price", value=ingr_price, min_value=0.0, key=f"p_{name}")
                weight_val = cols[4].number_input(f"{name}_weight", value=ingr_weight, min_value=1.0, key=f"w_{name}")
                if price_val != ingr_price or weight_val != ingr_weight:
                    save_price(name, price_val, weight_val)
                    ingr_price, ingr_weight = price_val, weight_val
                    updated = True
                # Вартість
                if unit in ["g", "ml"]:
                    price_per_g = price_val / weight_val if weight_val else 0
                    cost = price_per_g * amt
                else:
                    cost = price_val * amt / weight_val if weight_val else 0
                total_cost += cost
                # Поживність
                nutr = get_nutrition(name)
                ingr_cals.append(nutr.get("calories", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("calories", 0) * amt)
                ingr_prot.append(nutr.get("protein", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("protein", 0) * amt)
                ingr_fat.append(nutr.get("fat", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("fat", 0) * amt)
                ingr_carb.append(nutr.get("carbs", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("carbs", 0) * amt)
                cols[5].write(f"{cost:.2f}")
            st.header("📊 Аналіз страви (на 1 особу)")
            st.write(f"**Вартість:** CAD {total_cost/servings:.2f}")
            st.write(f"**Калорії:** {sum(ingr_cals)/servings:.0f} kcal")
            st.write(f"**Білки:** {sum(ingr_prot)/servings:.1f} г")
            st.write(f"**Жири:** {sum(ingr_fat)/servings:.1f} г")
            st.write(f"**Вуглеводи:** {sum(ingr_carb)/servings:.1f} г")
            if updated:
                st.success("Збережено нову ціну!")

# --- ДОДАВАННЯ РЕЦЕПТУ ---
if mode == "Додати рецепт":
    st.subheader("Новий рецепт")
    name = st.text_input("Назва страви")
    servings = st.number_input("Кількість порцій", value=1, min_value=1)
    ingr_block = st.text_area("Інгредієнти (формат: name,amount,unit; по рядку)")
    instructions = st.text_area("Інструкції приготування")
    if st.button("Додати рецепт"):
        # Парсимо інгредієнти
        ingr_list = []
        for line in ingr_block.strip().split("\n"):
            parts = [x.strip() for x in line.split(",")]
            if len(parts) == 3:
                ingr_list.append({"name": parts[0], "amount": float(parts[1]), "unit": parts[2]})
        if name and ingr_list:
            add_recipe(name, servings, ingr_list, instructions)
            st.success(f"Додано рецепт {name}!")
        else:
            st.error("Заповніть усі поля та додайте хоча б один інгредієнт.")

# --- РЕДАГУВАННЯ ЦІН ---
if mode == "Редагувати ціни":
    st.subheader("Ціни на інгредієнти")
    prices = get_prices()
    all_names = list(prices.keys()) + ["(новий інгредієнт)"]
    sel_name = st.selectbox("Оберіть інгредієнт для редагування:", all_names)
    if sel_name == "(новий інгредієнт)":
        name = st.text_input("Назва нового інгредієнта")
        price = st.number_input("Ціна (CAD)", min_value=0.0)
        weight = st.number_input("Вага пачки (г/мл/шт)", min_value=1.0)
        if st.button("Зберегти"):
            save_price(name, price, weight)
            st.success(f"Збережено {name}")
    elif sel_name:
        price = st.number_input("Ціна (CAD)", value=float(prices[sel_name]["price"]), min_value=0.0)
        weight = st.number_input("Вага пачки (г/мл/шт)", value=float(prices[sel_name]["weight"]), min_value=1.0)
        if st.button("Оновити"):
            save_price(sel_name, price, weight)
            st.success(f"Оновлено {sel_name}")

# --- ЗАВАНТАЖЕННЯ БД ---
if mode == "Завантажити базу":
    with open(DB_PATH, "rb") as f:
        st.download_button("⬇️ Завантажити всю базу даних (SQLite)", data=f, file_name="meals_db.sqlite")
    st.info("Цей файл можна перенести на інший ПК і продовжити працювати без втрати даних!")

