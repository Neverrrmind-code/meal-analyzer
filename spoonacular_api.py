import requests

def get_recipe(api_key, query):
    # Спочатку шукаємо рецепти
    search_url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "apiKey": api_key,
        "query": query,
        "number": 1
    }
    res = requests.get(search_url, params=params)
    res.raise_for_status()
    data = res.json()
    if not data.get("results"):
        return None
    recipe_id = data["results"][0]["id"]

    # Другий запит - отримати повну інформацію
    info_url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
    params_info = {"apiKey": api_key}
    res_info = requests.get(info_url, params=params_info)
    res_info.raise_for_status()
    recipe = res_info.json()
    # Структуруємо інгредієнти
    ingredients = {}
    for ingr in recipe["extendedIngredients"]:
        name = ingr.get("nameClean") or ingr["name"]
        amount = ingr["measures"]["metric"]["amount"]
        unit = ingr["measures"]["metric"]["unitShort"] or "g"
        ingredients[name.title()] = {"qty": amount, "unit": unit}
    return {
        "title": recipe["title"],
        "ingredients": ingredients,
        "servings": recipe["servings"]
    }
