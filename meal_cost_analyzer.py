import streamlit as st
import json
import os
import requests
from datetime import datetime

# ========== SPOONACULAR & USDA API ==========
def search_recipes(api_key, query, number=5):
    """Повертає список dict [{id, title}]"""
    url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "apiKey": api_key,
        "query": query,
        "number": number
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    data = res.json()
    return data.get("results", [])

def get_recipe_info(api_key, recipe_id):
    """Повертає повну інформацію про рецепт (інгредієнти, інструкції...)"""
    url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
    params = {"apiKey": api_key}
    res = requests.get(url, params=params)
    res.raise_for_status()
    recipe = res.json()
    ingredients = {}
    for ingr in recipe["extendedIngredients"]:
        name = ingr.get("nameClean") or ingr["name"]
        amount = ingr["measures"]["metric"]["amount"]
        unit = ingr["measures"]["metric"]["unitShort"] or "g"
        ingredients[name.title()] = {"qty": amount, "unit": unit}
    # Інструкції як кроки
    steps = []
    for analyzed in recipe.get("analyzedInstructions", []):
        for step in analyzed.get("steps", []):
            steps.append(step["step"])
    full_instructions = "\n".join(steps) if steps else (recipe.get("instructions") or "")
    return {
        "title": recipe["title"],
        "ingredients": ingredients,
        "servings": recipe["servings"],
        "instructions": full_instructions
    }

def search_usda_nutrition(api_key, ingredient_name):
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {
        "api_key": api_key,
        "query": ingredient_name,
        "pageSize": 1
    }
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        data = res.json()
        if not data.get("foods"): return None
        nutrients = {n["nutrientName"]: n["value"] for n in data["foods"][0].get("foodNutrients", [])}
        return {
            "calories": nutrients.get("Energy", 0),
            "protein": nutrients.get("Protein", 0),
            "fat": nutrients.get("Total lipid (fat)", 0),
            "carbs": nutrients.get("Carbohydrate, by difference", 0)
        }
    except Exception as e:
        return None

# ========== CONFIG & DB ==========
SPOONACULAR_KEY = st.secrets.get("spoonacular_key")
USDA_KEY = st.secrets.get("usda_api_key")
if not SPOONACULAR_KEY:
    st.error("Spoonacular API key not found! Set 'spoonacular_key' in .streamlit/secrets.toml or Streamlit Cloud Secrets.")
    st.stop()
if not USDA_KEY:
    st.warning("USDA API key не знайдено. Автозаповнення нутрієнтів не буде працювати.")

INGREDIENTS_FILE = "ingredients_db.json"
RECIPES_FILE = "recipes_db.json"

def init_db():
    if not os.path.exists(INGREDIENTS_FILE):
        with open(INGREDIENTS_FILE, "w") as f:
            json.dump({}, f)
    if not os.path.exists(RECIPES_FILE):
        with open(RECIPES_FILE, "w") as f:
            json.dump({}, f)

def load_json(file):
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

init_db()
ingredients = load_json(INGREDIENTS_FILE)
recipes = load_json(RECIPES_FILE)

st.title("🍲 Meal Cost & Nutrition Analyzer (Spoonacular+USDA)")
st.write("Шукай рецепти онлайн, підтягуй інгредієнти й інструкцію, оцінюй ціну та поживність!")

# --- 1. Пошук і імпорт рецепту зі Spoonacular
st.header("1. 📥 Пошук та імпорт рецепту з публічної бази")
query = st.text_input("Введи назву страви для пошуку (англійською):")
search_results = []
if st.button("🔍 Знайти рецепти") and query:
    try:
        search_results = search_recipes(SPOONACULAR_KEY, query)
        if not search_results:
            st.warning("Не знайдено жодного рецепта.")
    except Exception as e:
        st.error(f"Помилка при пошуку: {e}")

# Якщо знайдено кілька рецептів — даємо вибрати один:
if search_results:
    st.write("### Результати пошуку:")
    options = {f"{r['title']} (ID:{r['id']})": r["id"] for r in search_results}
    selected = st.selectbox("Оберіть рецепт для імпорту:", list(options.keys()))
    if st.button("📥 Імпортувати обраний рецепт"):
        recipe_id = options[selected]
        rec = get_recipe_info(SPOONACULAR_KEY, recipe_id)
        if rec:
            recipes[rec["title"]] = {
                "ingredients": {k: v["qty"] for k,v in rec["ingredients"].items()},
                "units": {k: v["unit"] for k,v in rec["ingredients"].items()},
                "servings": rec["servings"],
                "instructions": rec["instructions"]
            }
            save_json(RECIPES_FILE, recipes)
            st.success(f"Рецепт '{rec['title']}' додано!")
            st.experimental_rerun()
        else:
            st.warning("Не вдалося імпортувати рецепт.")

# --- 2. Аналіз і редагування інгредієнтів у таблиці
st.header("2. 🍛 Аналіз рецепту")
selected_recipe = st.selectbox("Оберіть рецепт", list(recipes.keys()))
if selected_recipe:
    rec = recipes[selected_recipe]
    servings = rec["servings"]

    st.subheader("Інгредієнти та ціна (редагування у таблиці):")
    ingr_names = list(rec["ingredients"].keys())
    table = []

    with st.form("edit_ingredients_table"):
        cols = st.columns([3, 2, 2, 2, 2, 2, 2, 2])
        # Header
        cols[0].markdown("**Інгредієнт**")
        cols[1].markdown("**Кількість**")
        cols[2].markdown("**Одиниця**")
        cols[3].markdown("**Ціна за упаковку (CAD)**")
        cols[4].markdown("**Вага упаковки**")
        cols[5].markdown("**Calories/100g**")
        cols[6].markdown("**Protein**")
        cols[7].markdown("**Carbs**")

        cost_total = 0.0
        new_ingredients = ingredients.copy()
        for ingr in ingr_names:
            qty = rec["ingredients"][ingr]
            unit = rec.get("units", {}).get(ingr, "g")
            ingr_data = new_ingredients.get(ingr, {})
            price = ingr_data.get("price", 0.0)
            weight = ingr_data.get("weight", 0.0)
            calories = ingr_data.get("calories", 0.0)
            protein = ingr_data.get("protein", 0.0)
            fat = ingr_data.get("fat", 0.0)
            carbs = ingr_data.get("carbs", 0.0)
            # Поля для редагування
            cols = st.columns([3, 2, 2, 2, 2, 2, 2, 2])
            cols[0].write(ingr)
            cols[1].write(f"{qty}")
            cols[2].write(unit)
            price_val = cols[3].number_input(f"price_{ingr}", value=float(price), min_value=0.0, step=0.1, key=f"price_{ingr}")
            weight_val = cols[4].number_input(f"weight_{ingr}", value=float(weight), min_value=1.0, step=1.0, key=f"weight_{ingr}")

            # --- Автозаповнення нутрієнтів через USDA (тільки якщо пусто)
            if USDA_KEY and (not calories and not protein and not fat and not carbs):
                usda = search_usda_nutrition(USDA_KEY, ingr)
                if usda:
                    calories = usda["calories"]
                    protein = usda["protein"]
                    fat = usda["fat"]
                    carbs = usda["carbs"]
            calories_val = cols[5].number_input(f"cal_{ingr}", value=float(calories), step=1.0, key=f"cal_{ingr}")
            protein_val = cols[6].number_input(f"prot_{ingr}", value=float(protein), step=0.1, key=f"prot_{ingr}")
            carbs_val   = cols[7].number_input(f"carb_{ingr}", value=float(carbs), step=0.1, key=f"carb_{ingr}")

            # Оновлюємо копію
            new_ingredients[ingr] = {
                **ingr_data, "price": price_val, "weight": weight_val, "unit": unit,
                "calories": calories_val, "protein": protein_val, "carbs": carbs_val,
                "fat": fat
            }
            # Розрахунок вартості
            price_per_g = price_val / weight_val if weight_val else 0
            cost = price_per_g * qty
            cost_total += cost
            table.append([ingr, qty, unit, price_val, weight_val, calories_val, protein_val, carbs_val, cost])

        save_btn = st.form_submit_button("💾 Зберегти всі зміни")
        if save_btn:
            ingredients.update(new_ingredients)
            save_json(INGREDIENTS_FILE, ingredients)
            st.success("Збережено зміни до інгредієнтів!")
            st.experimental_rerun()

    st.write("### Підсумкова таблиця")
    st.dataframe(
        { "Інгредієнт": [row[0] for row in table],
          "Кількість": [row[1] for row in table],
          "Одиниця": [row[2] for row in table],
          "Ціна, CAD": [row[3] for row in table],
          "Вага упаковки": [row[4] for row in table],
          "Calories/100g": [row[5] for row in table],
          "Protein": [row[6] for row in table],
          "Carbs": [row[7] for row in table],
          "Вартість, CAD": [row[8] for row in table]
        },
        hide_index=True
    )
    st.write(f"**Вартість однієї порції:** CAD {cost_total/servings:.2f}")

    # Показати інструкцію
    if "instructions" in rec and rec["instructions"]:
        st.subheader("📖 Інструкція приготування")
        st.write(rec["instructions"])

# --- 3. Редагування інгредієнтів (повний режим)
with st.expander("⚙️ Додати/Редагувати інгредієнти та нутрієнти (advanced)"):
    name = st.text_input("Інгредієнт")
    if name:
        price = st.number_input("Price (CAD)", min_value=0.0)
        weight = st.number_input("Weight (in unit)", min_value=1.0)
        unit = st.selectbox("Unit", ["g"]()
