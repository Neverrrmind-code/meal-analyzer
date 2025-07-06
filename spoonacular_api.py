# spoonacular_api.py

import requests

def get_recipe(api_key, query):
    url = f"https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "apiKey": api_key,
        "query": query,
        "addRecipeInformation": True,
        "number": 1
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    data = res.json()
    if not data.get("results"):
        return None
    recipe = data["results"][0]
    # Structure ingredients as: {ingredient_name: amount_in_metric}
    ingredients = {}
    for ingr in recipe["extendedIngredients"]:
        name = ingr["nameClean"] or ingr["name"]
        amount = ingr["measures"]["metric"]["amount"]
        unit = ingr["measures"]["metric"]["unitShort"] or "g"
        ingredients[name.title()] = {"qty": amount, "unit": unit}
    return {
        "title": recipe["title"],
        "ingredients": ingredients,
        "servings": recipe["servings"]
    }
