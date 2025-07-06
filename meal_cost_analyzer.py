# meal_cost_analyzer: Streamlit MVP

import streamlit as st
import json
import requests
import os
from datetime import datetime

# Local DB paths
INGREDIENTS_FILE = "ingredients_db.json"
RECIPES_FILE = "recipes_db.json"

# Initialize files if they don't exist
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

# 🔄 Ensure DB files exist before loading
init_db()

# 🔽 Load data from JSON
ingredients = load_json(INGREDIENTS_FILE)
recipes = load_json(RECIPES_FILE)

# 🌐 Streamlit UI
st.title("🍲 Meal Cost & Nutrition Analyzer")
st.write("Track cost and nutrition of meals using Costco (Winnipeg) prices")

# Add new ingredient
st.header("1. 🛒 Add Ingredient")
with st.form("add_ingredient"):
    name = st.text_input("Ingredient name")
    price = st.number_input("Price (CAD)", min_value=0.0)
    weight = st.number_input("Weight (g)", min_value=1)
    calories = st.number_input("Calories per 100g", min_value=0)
    protein = st.number_input("Protein per 100g", min_value=0.0)
    fat = st.number_input("Fat per 100g", min_value=0.0)
    carbs = st.number_input("Carbs per 100g", min_value=0.0)
    submitted = st.form_submit_button("Add Ingredient")
    if submitted and name:
        ingredients[name] = {
            "price": price,
            "weight": weight,
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
    qty = st.number_input(f"{ingr} amount (g)", key=ingr)
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
        price_per_g = i["price"] / i["weight"]
        total_cost += price_per_g * qty
        total_cals += (i["calories"] / 100) * qty
        total_prot += (i["protein"] / 100) * qty
        total_fat += (i["fat"] / 100) * qty
        total_carb += (i["carbs"] / 100) * qty

    st.subheader(f"🍽️ {selected_recipe} — per serving")
    st.write(f"**Cost:** CAD {total_cost/data['servings']:.2f}")
    st.write(f"**Calories:** {total_cals/data['servings']:.0f} kcal")
    st.write(f"**Protein:** {total_prot/data['servings']:.1f} g")
    st.write(f"**Fat:** {total_fat/data['servings']:.1f} g")
    st.write(f"**Carbs:** {total_carb/data['servings']:.1f} g")
