#!/usr/bin/env python3
# price_predictor.py
"""
Trains a simple model from the QuotationItems joined with Products and persists it.
Provides predict_quote_total(product_list) used by the Flask app.
"""
import os
import pickle
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error
from sqlalchemy import create_engine, text
from pathlib import Path

MODEL_PATH = Path(os.getenv("PRICE_MODEL_PATH", "")) if os.getenv("PRICE_MODEL_PATH") else None

def _default_db_path():
    # instance/database.db relative to this file's parent (project root)
    here = Path(__file__).resolve().parent
    instance = here / "instance"
    return f"sqlite:///{instance / 'database.db'}"

def _get_engine(db_uri=None):
    return create_engine(db_uri or _default_db_path())

def train_and_save_model(db_uri=None, model_out_path=None):
    engine = _get_engine(db_uri)
    with engine.connect() as conn:
        # Pull training data: join quotation_items with products to get category and base cost
        query = text("""
            SELECT qi.quantity, qi.width_ft, qi.height_ft, qi.unit_price, qi.line_total,
                   p.category, p.base_cost_per_sqft
            FROM quotation_item AS qi
            JOIN product AS p ON qi.product_id = p.id
        """)
        rows = conn.execute(query).fetchall()

    if not rows:
        raise RuntimeError("No data available to train the price predictor. Seed the DB first.")

    import pandas as pd
    df = pd.DataFrame(rows, columns=['quantity','width_ft','height_ft','unit_price','line_total','category','base_cost_per_sqft'])
    # Features
    df['area'] = df['width_ft'] * df['height_ft']
    X = df[['category', 'area', 'quantity', 'base_cost_per_sqft']]
    y = df['line_total']  # predict line total and then sum for a quote

    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown='ignore'), ['category']),
        ("num", "passthrough", ['area', 'quantity', 'base_cost_per_sqft'])
    ])

    model = Pipeline(steps=[
        ("pre", pre),
        ("reg", LinearRegression())
    ])

    model.fit(X, y)

    preds = model.predict(X)
    mae = mean_absolute_error(y, preds)
    print(f"[price_predictor] Trained LinearRegression on {len(df)} rows. MAE={mae:.2f}")

    out_path = Path(model_out_path) if model_out_path else (Path(__file__).resolve().parent / "instance" / "price_model.pkl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump(model, f)
    return str(out_path)

def _load_model():
    # Try explicit MODEL_PATH env first
    if MODEL_PATH and MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    # else attempt instance/price_model.pkl relative to this file
    local_path = Path(__file__).resolve().parent / "instance" / "price_model.pkl"
    if local_path.exists():
        with open(local_path, "rb") as f:
            return pickle.load(f)
    # If missing, train from DB
    print("[price_predictor] Model not found. Training from DB...")
    train_and_save_model()
    with open(local_path, "rb") as f:
        return pickle.load(f)

_model_cache = None

def predict_quote_total(product_list):
    """
    product_list: list of dicts with keys:
        - category: str
        - width_ft: float
        - height_ft: float
        - quantity: int
        - base_cost_per_sqft: float (optional; if omitted, we use 0)
    Returns: float suggested total for the whole quote
    """
    global _model_cache
    if _model_cache is None:
        _model_cache = _load_model()

    import pandas as pd
    rows = []
    for item in product_list:
        area = float(item.get("width_ft", 0)) * float(item.get("height_ft", 0))
        rows.append({
            "category": item.get("category", "Unknown"),
            "area": area,
            "quantity": int(item.get("quantity", 1)),
            "base_cost_per_sqft": float(item.get("base_cost_per_sqft", 0.0)),
        })
    if not rows:
        return 0.0
    df = pd.DataFrame(rows)
    line_total_preds = _model_cache.predict(df)
    total = float(np.maximum(line_total_preds, 0).sum())
    return round(total, 2)
