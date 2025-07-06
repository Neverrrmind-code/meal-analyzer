import streamlit as st
import json
import os
from datetime import datetime
from spoonacular_api import get_recipe

SPOONACULAR_KEY = st.secrets["spoonacular_key"]
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

st.title("🍲 Meal Cost & Nutrition Analyzer (Spoonacular)")
st.write("Шукай рецепти онлайн, підтягуй інгредієнти й оцінюй їхню ціну та поживність!")

# --- 1. Імпорт рецепту зі Spoonacular
st.header("1. 📥 Імпорт рецепту з публічної бази")
query = st.text_input("Введи назву страви для пошуку (англійською):")
if st.button("Знайти та імпортувати рецепт") and query:
    rec = get_recipe(SPOONACULAR_KEY, query)
    if rec:
        # Додаємо рецепт до локальної БД
        recipes[rec["title"]] = {
            "ingredients": {k: v["qty"] for k,v in rec["ingredients"].items()},
            "units": {k: v["unit"] for k,v in rec["ingredients"].items()},
            "servings": rec["servings"]
        }
        save_json(RECIPES_FILE, recipes)
        st.success(f"Рецепт '{rec['title']}' додано!")
    else:
        st.warning("Рецепт не знайдено.")

# --- 2. Вибір рецепту для аналізу
st.header("2. 🍛 Аналіз рецепту")
selected_recipe = st.selectbox("Оберіть рецепт", list(recipes.keys()))
if selected_recipe:
    rec = recipes[selected_recipe]
    servings = rec["servings"]
    ingr_table = []
    total_cost = total_cals = total_prot = total_fat = total_carb = 0.0

        if "instructions" in rec and rec["instructions"]:
        st.subheader("📖 Інструкція приготування")
        st.write(rec["instructions"])

    for ingr, qty in rec["ingredients"].items():
        # unit
        unit = rec.get("units", {}).get(ingr, "g")
        # Check if in local ingredient DB
        if ingr not in ingredients:
            price = st.number_input(f"Ціна {ingr} ({unit}, за пакування):", min_value=0.0, key=f"price_{ingr}")
            weight = st.number_input(f"Вага пакування {ingr} ({unit}):", min_value=1.0, key=f"weight_{ingr}")
            # Додаємо пусті нутрієнти для майбутнього автоматичного/ручного заповнення
            ingredients[ingr] = {
                "price": price, "weight": weight,
                "unit": unit, "weight_per_unit": 1,
                "calories": 0, "protein": 0, "fat": 0, "carbs": 0,
                "updated": str(datetime.now())
            }
            save_json(INGREDIENTS_FILE, ingredients)
        else:
            price = ingredients[ingr]["price"]
            weight = ingredients[ingr]["weight"]

        price_per_g = price / weight if weight else 0
        cost = price_per_g * qty
        total_cost += cost
        ingr_table.append(f"{ingr}: {qty} {unit}, вартість: CAD {cost:.2f}")

    st.subheader("Інгредієнти та вартість (без нутрієнтів):")
    st.write("\n".join(ingr_table))
    st.write(f"Вартість однієї порції: **CAD {total_cost/servings:.2f}**")

# --- 3. Редагування інгредієнтів, нутрієнти
with st.expander("⚙️ Додати/Редагувати інгредієнти та нутрієнти"):
    name = st.text_input("Інгредієнт")
    if name:
        price = st.number_input("Price (CAD)", min_value=0.0)
        weight = st.number_input("Weight (in unit)", min_value=1.0)
        unit = st.selectbox("Unit", ["g", "ml", "pcs", "tbsp", "slice"])
        weight_per_unit = st.number_input("Grams per unit", min_value=1.0, value=1.0)
        calories = st.number_input("Calories per 100g", value=0.0)
        protein = st.number_input("Protein per 100g", value=0.0)
        fat = st.number_input("Fat per 100g", value=0.0)
        carbs = st.number_input("Carbs per 100g", value=0.0)
        if st.button("Save Ingredient (edit)"):
            ingredients[name] = {
                "price": price,
                "weight": weight,
                "unit": unit,
                "weight_per_unit": weight_per_unit,
                "calories": calories,
                "protein": protein,
                "fat": fat,
                "carbs": carbs,
                "updated": str(datetime.now())
            }
            save_json(INGREDIENTS_FILE, ingredients)
            st.success(f"Saved: {name}")

