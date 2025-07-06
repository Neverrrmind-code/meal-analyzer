import streamlit as st
import sqlite3
import json
import pandas as pd
import requests

DB_PATH = "meals_db.sqlite"
USDA_KEY = st.secrets.get("usda_api_key", "")

# ---- БАЗА ДАНИХ ----
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    servings INTEGER,
                    ingredients TEXT,     -- JSON [{'name':..,'amount':..,'unit':..}]
                    instructions TEXT
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS ingredient_prices (
                    name TEXT PRIMARY KEY,
                    price REAL,
                    weight REAL,
                    unit TEXT
                )""")
    conn.commit()
    conn.close()
init_db()

def get_conn():
    return sqlite3.connect(DB_PATH)

def get_all_recipes():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM recipes", conn)
    conn.close()
    return df

def add_recipe(name, servings, ingredients, instructions):
    conn = get_conn()
    conn.execute(
        "INSERT INTO recipes (name, servings, ingredients, instructions) VALUES (?, ?, ?, ?)",
        (name, servings, json.dumps(ingredients), instructions))
    conn.commit()
    conn.close()

def update_recipe(recipe_id, name, servings, ingredients, instructions):
    conn = get_conn()
    conn.execute(
        "UPDATE recipes SET name=?, servings=?, ingredients=?, instructions=? WHERE id=?",
        (name, servings, json.dumps(ingredients), instructions, recipe_id))
    conn.commit()
    conn.close()

def delete_recipe(recipe_id):
    conn = get_conn()
    conn.execute("DELETE FROM recipes WHERE id=?", (recipe_id,))
    conn.commit()
    conn.close()

def get_prices():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM ingredient_prices", conn)
    conn.close()
    return df

def save_price(name, price, weight, unit):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO ingredient_prices (name, price, weight, unit) VALUES (?, ?, ?, ?)",
        (name, price, weight, unit)
    )
    conn.commit()
    conn.close()

def delete_ingredient(name):
    conn = get_conn()
    conn.execute("DELETE FROM ingredient_prices WHERE name=?", (name,))
    conn.commit()
    conn.close()

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

st.title("🍲 Meal Cost & Nutrition Analyzer (SQLite, full CRUD)")

mode = st.sidebar.radio("Режим", [
    "Вибір рецепту", "Додати рецепт", "Редагувати/видалити рецепт",
    "Ціни продуктів", "Додати/видалити продукт",
    "Завантажити базу"
])

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
            df_prices = get_prices()
            price_dict = {row["name"]: row for idx, row in df_prices.iterrows()}

            # --- РЕДАГУВАННЯ ЦІН У ТАБЛИЦІ ---
            st.write("### Всі ціни на продукти (можна редагувати):")
            df_edit = df_prices.copy()
            edited = st.data_editor(
                df_edit, key="edit_prices",
                column_config={
                    "price": st.column_config.NumberColumn("Ціна (CAD)", min_value=0),
                    "weight": st.column_config.NumberColumn("Вага (г/мл/шт)", min_value=1),
                    "unit": st.column_config.TextColumn("Одиниця (г/мл/шт/л/pcs/...)")
                },
                num_rows="dynamic"
            )
            if st.button("💾 Зберегти зміни цін"):
                for _, row in edited.iterrows():
                    if row["name"]:
                        save_price(row["name"], row["price"], row["weight"], row["unit"])
                st.success("Оновлено всі ціни/одиниці!")

            # --- Аналіз інгредієнтів по рецепту ---
            total_cost = 0.0
            ingr_cals, ingr_prot, ingr_fat, ingr_carb = [], [], [], []
            for ingr in ingr_list:
                name = ingr["name"]
                amt = float(ingr.get("amount", 0))
                unit = ingr.get("unit", "g")
                p = price_dict.get(name, {"price":0, "weight":100, "unit":unit})
                ingr_price, ingr_weight, price_unit = float(p["price"]), float(p["weight"]), p.get("unit", unit)
                # Конвертація, якщо одиниці не співпадають (простий випадок)
                if price_unit != unit:
                    st.warning(f"Одиниця {name}: рецепт {unit}, ціна {price_unit}. Контроль потрібен вручну.")
                # Вартість
                if unit in ["g", "ml"]:
                    price_per_g = ingr_price / ingr_weight if ingr_weight else 0
                    cost = price_per_g * amt
                else:
                    cost = ingr_price * amt / ingr_weight if ingr_weight else 0
                total_cost += cost
                # Поживність
                nutr = get_nutrition(name)
                ingr_cals.append(nutr.get("calories", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("calories", 0) * amt)
                ingr_prot.append(nutr.get("protein", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("protein", 0) * amt)
                ingr_fat.append(nutr.get("fat", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("fat", 0) * amt)
                ingr_carb.append(nutr.get("carbs", 0) * amt / 100 if unit in ["g", "ml"] else nutr.get("carbs", 0) * amt)
            st.header("📊 Аналіз страви (на 1 особу)")
            st.write(f"**Вартість:** CAD {total_cost/servings:.2f}")
            st.write(f"**Калорії:** {sum(ingr_cals)/servings:.0f} kcal")
            st.write(f"**Білки:** {sum(ingr_prot)/servings:.1f} г")
            st.write(f"**Жири:** {sum(ingr_fat)/servings:.1f} г")
            st.write(f"**Вуглеводи:** {sum(ingr_carb)/servings:.1f} г")

# --- ДОДАТИ РЕЦЕПТ ---
if mode == "Додати рецепт":
    st.subheader("Новий рецепт")
    name = st.text_input("Назва страви")
    servings = st.number_input("Кількість порцій", value=1, min_value=1)
    ingr_block = st.text_area("Інгредієнти (формат: name,amount,unit; по рядку)")
    instructions = st.text_area("Інструкції приготування")
    if st.button("Додати рецепт"):
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

# --- РЕДАГУВАТИ/ВИДАЛИТИ РЕЦЕПТ ---
if mode == "Редагувати/видалити рецепт":
    df = get_all_recipes()
    if not df.empty:
        row = st.selectbox("Оберіть рецепт для редагування/видалення:", df["name"].tolist())
        recipe_row = df[df["name"] == row].iloc[0]
        rid = recipe_row["id"]
        name = st.text_input("Назва страви", value=recipe_row["name"])
        servings = st.number_input("Кількість порцій", value=int(recipe_row["servings"]), min_value=1)
        ingr_block = st.text_area(
            "Інгредієнти (формат: name,amount,unit; по рядку)",
            value="\n".join(f"{i['name']},{i['amount']},{i['unit']}" for i in json.loads(recipe_row["ingredients"]))
        )
        instructions = st.text_area("Інструкції", value=recipe_row["instructions"])
        if st.button("Оновити рецепт"):
            ingr_list = []
            for line in ingr_block.strip().split("\n"):
                parts = [x.strip() for x in line.split(",")]
                if len(parts) == 3:
                    ingr_list.append({"name": parts[0], "amount": float(parts[1]), "unit": parts[2]})
            update_recipe(rid, name, servings, ingr_list, instructions)
            st.success("Оновлено!")
        if st.button("❌ Видалити рецепт"):
            delete_recipe(rid)
            st.success("Видалено рецепт.")

# --- РЕДАГУВАТИ ВСІ ПРОДУКТИ ---
if mode == "Ціни продуктів":
    df = get_prices()
    if not df.empty:
        st.write("### Всі продукти (натисни на клітинку для редагування):")
        df_edit = df.copy()
        edited = st.data_editor(
            df_edit, key="edit_all_ings",
            column_config={
                "price": st.column_config.NumberColumn("Ціна (CAD)", min_value=0),
                "weight": st.column_config.NumberColumn("Вага (г/мл/шт)", min_value=1),
                "unit": st.column_config.TextColumn("Одиниця (г/мл/шт/л/pcs/...)")
            },
            num_rows="dynamic"
        )
        if st.button("💾 Зберегти зміни (всі продукти)"):
            for _, row in edited.iterrows():
                if row["name"]:
                    save_price(row["name"], row["price"], row["weight"], row["unit"])
            st.success("Оновлено всі ціни/одиниці!")
    else:
        st.info("Ще немає жодного продукту.")

# --- ДОДАТИ/ВИДАЛИТИ ПРОДУКТ ---
if mode == "Додати/видалити продукт":
    st.subheader("Додати або видалити продукт")
    name = st.text_input("Назва продукту")
    price = st.number_input("Ціна (CAD)", min_value=0.0)
    weight = st.number_input("Вага пачки (г/мл/шт)", min_value=1.0)
    unit = st.selectbox("Одиниця", ["g", "ml", "pcs", "tbsp", "slice", "l", "шт"])
    if st.button("Додати/оновити продукт"):
        if name:
            save_price(name, price, weight, unit)
            st.success(f"Додано/оновлено продукт: {name}")
    if st.button("❌ Видалити продукт"):
        if name:
            delete_ingredient(name)
            st.success(f"Видалено продукт: {name}")

# --- ЗАВАНТАЖЕННЯ БД ---
if mode == "Завантажити базу":
    with open(DB_PATH, "rb") as f:
        st.download_button("⬇️ Завантажити всю базу даних (SQLite)", data=f, file_name="meals_db.sqlite")
    st.info("Цей файл можна перенести на інший ПК і продовжити працювати без втрати даних!")

