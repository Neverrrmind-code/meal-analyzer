import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path

# Ініціалізація бази даних
DB_FILE = Path("food_prices.db")

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                unit TEXT NOT NULL,
                price_per_unit REAL NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS recipe_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER,
                product_id INTEGER,
                quantity REAL,
                FOREIGN KEY(recipe_id) REFERENCES recipes(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        ''')
        conn.commit()

# Функція імпорту продуктів з CSV
@st.cache_data
def import_csv(csv_file):
    df = pd.read_csv(csv_file)
    with sqlite3.connect(DB_FILE) as conn:
        df.to_sql('products', conn, if_exists='append', index=False)

# Додавання продукту
def add_product(name, unit, price):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO products (name, unit, price_per_unit) VALUES (?, ?, ?)", (name, unit, price))
        conn.commit()

# Отримання списку продуктів
def get_products():
    with sqlite3.connect(DB_FILE) as conn:
        return pd.read_sql("SELECT * FROM products", conn)

# Додавання рецепту
def add_recipe(name):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO recipes (name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid

# Додавання інгредієнта до рецепту
def add_recipe_item(recipe_id, product_id, quantity):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO recipe_items (recipe_id, product_id, quantity) VALUES (?, ?, ?)", (recipe_id, product_id, quantity))
        conn.commit()

# Розрахунок вартості порції
def calculate_recipe_cost(recipe_id):
    with sqlite3.connect(DB_FILE) as conn:
        query = '''
            SELECT p.name, ri.quantity, p.unit, p.price_per_unit,
                   (ri.quantity * p.price_per_unit) as total_cost
            FROM recipe_items ri
            JOIN products p ON p.id = ri.product_id
            WHERE ri.recipe_id = ?
        '''
        df = pd.read_sql(query, conn, params=(recipe_id,))
        total = df['total_cost'].sum()
        return df, total

# Streamlit UI
st.title("Food Cost Calculator")

init_db()

menu = st.sidebar.selectbox("Menu", ["Import CSV", "Add Product", "Create Recipe", "View Recipe Cost"])

if menu == "Import CSV":
    file = st.file_uploader("Upload CSV with columns: name, unit, price_per_unit")
    if file:
        import_csv(file)
        st.success("CSV Imported Successfully")

elif menu == "Add Product":
    name = st.text_input("Product Name")
    unit = st.selectbox("Unit", ["g", "kg", "pcs", "ml", "l"])
    price = st.number_input("Price per Unit", min_value=0.0)
    if st.button("Add Product"):
        add_product(name, unit, price)
        st.success("Product Added")

elif menu == "Create Recipe":
    recipe_name = st.text_input("Recipe Name")
    if st.button("Create Recipe"):
        recipe_id = add_recipe(recipe_name)
        st.session_state["recipe_id"] = recipe_id
        st.success(f"Recipe '{recipe_name}' created")

    if "recipe_id" in st.session_state:
        products = get_products()
        product_name = st.selectbox("Select Product", products['name'])
        product_id = products[products['name'] == product_name]['id'].values[0]
        quantity = st.number_input("Quantity", min_value=0.0)
        if st.button("Add to Recipe"):
            add_recipe_item(st.session_state["recipe_id"], product_id, quantity)
            st.success("Product added to recipe")

elif menu == "View Recipe Cost":
    with sqlite3.connect(DB_FILE) as conn:
        recipes = pd.read_sql("SELECT * FROM recipes", conn)
    recipe_name = st.selectbox("Select Recipe", recipes['name'])
    recipe_id = recipes[recipes['name'] == recipe_name]['id'].values[0]
    df, total = calculate_recipe_cost(recipe_id)
    st.dataframe(df)
    st.write(f"### Total Cost per Serving: ${total:.2f}")
