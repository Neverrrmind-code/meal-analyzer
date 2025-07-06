# meal_cost_analyzer: Streamlit MVP — with public recipe base + full USDA autofill

import streamlit as st
import json
import os
import requests
from datetime import datetime

INGREDIENTS_FILE = "ingredients_db.json"
RECIPES_FILE = "recipes_db.json"
USDA_API_KEY = st.secrets["usda_api_key"] if "usda_api_key" in st.secrets else "YOUR_API_KEY_HERE"

# Public recipe demo (can be replaced by actual API)
PUBLIC_RECIPES = {
    "Omelette": {
        "ingredients": {"Egg": 2, "Milk": 50, "Butter": 10}, "servings": 1
    },
    "Banana Smoothie": {
        "ingredients": {"Banana": 1, "Milk": 200, "Honey": 10}, "servings": 1
    },
    "Potato Soup": {
        "ingredients": {"Potato": 300, "Onion": 50, "Butter": 20, "Salt": 5}, "servings": 2
    }
}

# Initialize DB files if they don't exist
def init_db():
    if not os.path.exists(INGREDIENTS_FILE):
        with open(INGREDIENTS_FILE, "w") as f:
            json.dump({}, f)
    if not os.path.exists(RECIPES_FILE):
        with open(RECIPES_FILE, "w") as f:
            json.dump(PUBLIC_RECIPES, f)

def load_json(file):
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# Search nutrition from USDA
@st.cache_data(show_spinner=False)
def search_usda(query):
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search?query={query}&pageSize=1&api_key={USDA_API_KEY}"
    try:
        res = requests.get(url)
        item = res.json()["foods"][0]
        nutrients = {n["nutrientName"]: n["value"] for n in item["foodNutrients"]}
        return {
            "calories": nutrients.get("Energy", 0),
            "protein": nutrients.get("Protein", 0),
            "fat": nutrients.get("Total lipid (fat)", 0),
            "carbs": nutrients.get("Carbohydrate, by difference", 0)
        }
    except:
        return {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}

init_db()
ingredients = load_json(INGREDIENTS_FILE)
recipes = load_json(RECIPES_FILE)

st.title("🍲 Meal Cost & Nutrition Analyzer")
st.write("Analyze real meals by price, calories, protein, carbs and fats")

# Select recipe first
st.header("1. 🍛 Select Recipe")
selected_recipe = st.selectbox("Choose recipe", list(recipes.keys()))

if selected_recipe:
    recipe_data = recipes[selected_recipe]
    servings = recipe_data["servings"]
    st.markdown(f"**Servings:** {servings}")

    # Show ingredient table and update/add missing ones
    st.subheader("📦 Ingredients")
    total_cost = 0.0
    total_cals = 0.0
    total_prot = 0.0
    total_fat = 0.0
    total_carb = 0.0

    for ingr, qty in recipe_data["ingredients"].items():
        if ingr not in ingredients:
            # Auto-fetch from USDA if missing
            usda = search_usda(ingr)
            ingredients[ingr] = {
                "price": 0.0,
                "weight": 100,
                "unit": "g",
                "weight_per_unit": 1,
                "calories": usda["calories"],
                "protein": usda["protein"],
                "fat": usda["fat"],
                "carbs": usda["carbs"],
                "updated": str(datetime.now())
            }
            save_json(INGREDIENTS_FILE, ingredients)

        i = ingredients[ingr]
        unit_weight = i["weight_per_unit"] if i["unit"] != "g" else 1
        qty_in_grams = qty * unit_weight
        price_per_g = i["price"] / (i["weight"] * unit_weight if i["unit"] != "g" else i["weight"] or 1)
        total_cost += price_per_g * qty_in_grams
        total_cals += (i["calories"] / 100) * qty_in_grams
        total_prot += (i["protein"] / 100) * qty_in_grams
        total_fat += (i["fat"] / 100) * qty_in_grams
        total_carb += (i["carbs"] / 100) * qty_in_grams

        st.write(f"{ingr}: {qty} {i['unit']} — CAD {price_per_g * qty_in_grams:.2f}, {i['calories']} kcal/100g")

    st.subheader("📊 Analysis — per serving")
    st.write(f"**Cost:** CAD {total_cost/servings:.2f}")
    st.write(f"**Calories:** {total_cals/servings:.0f} kcal")
    st.write(f"**Protein:** {total_prot/servings:.1f} g")
    st.write(f"**Fat:** {total_fat/servings:.1f} g")
    st.write(f"**Carbs:** {total_carb/servings:.1f} g")

# Admin section to add/update manually
with st.expander("⚙️ Add or Edit Ingredient"):
    name = st.text_input("Ingredient name")
    if name:
        usda = search_usda(name)
        price = st.number_input("Price (CAD)", min_value=0.0)
        weight = st.number_input("Weight (in unit)", min_value=1, value=100)
        unit = st.selectbox("Unit", ["g", "ml", "pcs", "tbsp", "slice"])
        weight_per_unit = st.number_input("Grams per unit", min_value=1, value=1)
        calories = st.number_input("Calories per 100g", value=usda["calories"])
        protein = st.number_input("Protein per 100g", value=usda["protein"])
        fat = st.number_input("Fat per 100g", value=usda["fat"])
        carbs = st.number_input("Carbs per 100g", value=usda["carbs"])
        if st.button("Save Ingredient"):
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
