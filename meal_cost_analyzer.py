# meal_cost_analyzer: Streamlit MVP — with unit support and USDA API

import streamlit as st
import json
import os
import requests
from datetime import datetime

INGREDIENTS_FILE = "ingredients_db.json"
RECIPES_FILE = "recipes_db.json"
USDA_API_KEY = st.secrets["usda_api_key"] if "usda_api_key" in st.secrets else "YOUR_API_KEY_HERE"

# Initialize DB files if they don't exist
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
st.write("Track cost and nutrition of meals using Costco (Winnipeg) prices")

# Add new ingredient
st.header("1. 🛒 Add Ingredient")
with st.form("add_ingredient"):
    name = st.text_input("Ingredient name")
    price = st.number_input("Price (CAD)", min_value=0.0)
    weight = st.number_input("Weight (in unit)", min_value=1)
    unit = st.selectbox("Unit", ["g", "ml", "pcs", "tbsp", "slice"])
    weight_per_unit = 1
    if unit != "g":
        weight_per_unit = st.number_input("Grams per unit (e.g. 1 egg ≈ 60g)", min_value=1)

    use_usda = st.checkbox("Auto-fill nutrition from USDA")
    if use_usda and name:
        usda_data = search_usda(name)
        calories = usda_data["calories"]
        protein = usda_data["protein"]
        fat = usda_data["fat"]
        carbs = usda_data["carbs"]
        st.success("Auto-filled from USDA")
    else:
        calories = st.number_input("Calories per 100g", min_value=0)
        protein = st.number_input("Protein per 100g", min_value=0.0)
        fat = st.number_input("Fat per 100g", min_value=0.0)
        carbs = st.number_input("Carbs per 100g", min_value=0.0)

    submitted = st.form_submit_button("Add Ingredient")
    if submitted and name:
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
        st.success(f"Added {name} to database")

# Add recipe
st.header("2. 🍛 Create Recipe")
recipe_name = st.text_input("Recipe name")
selected_ingredients = st.multiselect("Choose ingredients", list(ingredients.keys()))
ingr_quantities = {}
for ingr in selected_ingredients:
    ing = ingredients[ingr]
    qty = st.number_input(f"{ingr} amount ({ing['unit']})", key=ingr)
    ingr_quantities[ingr] = qty
servings = st.number_input("Servings", min_value=1, value=1)
if st.button("Save Recipe") and recipe_name and selected_ingredients:
    recipes[recipe_name] = {
        "ingredients": ingr_quantities,
        "servings": servings
    }
    save_json(RECIPES_FILE, recipes)
    st.success(f"Saved recipe: {recipe_name}")

# View recipe results
st.header("3. 📊 Analyze Recipes")
selected_recipe = st.selectbox("Choose recipe to analyze", list(recipes.keys()))
if selected_recipe:
    data = recipes[selected_recipe]
    total_cost = 0.0
    total_cals = 0.0
    total_prot = 0.0
    total_fat = 0.0
    total_carb = 0.0

    for ingr, qty in data["ingredients"].items():
        i = ingredients[ingr]
        unit_weight = i["weight_per_unit"] if i["unit"] != "g" else 1
        qty_in_grams = qty * unit_weight
        price_per_g = i["price"] / (i["weight"] * unit_weight if i["unit"] != "g" else i["weight"])
        total_cost += price_per_g * qty_in_grams
        total_cals += (i["calories"] / 100) * qty_in_grams
        total_prot += (i["protein"] / 100) * qty_in_grams
        total_fat += (i["fat"] / 100) * qty_in_grams
        total_carb += (i["carbs"] / 100) * qty_in_grams

    st.subheader(f"🍽️ {selected_recipe} — per serving")
    st.write(f"**Cost:** CAD {total_cost/data['servings']:.2f}")
    st.write(f"**Calories:** {total_cals/data['servings']:.0f} kcal")
    st.write(f"**Protein:** {total_prot/data['servings']:.1f} g")
    st.write(f"**Fat:** {total_fat/data['servings']:.1f} g")
    st.write(f"**Carbs:** {total_carb/data['servings']:.1f} g")
