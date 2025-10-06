#!/usr/bin/env python3
# customer_segmentation.py
"""
Compute simple customer segments (clusters) using scikit-learn.
Features per customer:
- total_quotes        (count)
- total_value         (sum of quotation totals)
- avg_value           (mean of quotation totals)
- days_since_last     (recency in days; larger = more inactive)

Returns a DataFrame with a human-friendly segment label per cluster.
"""
from __future__ import annotations
from typing import Optional, List, Dict
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from models import Customer, Quotation

def _utcnow() -> datetime:
    try:
        return datetime.now(timezone.utc)
    except Exception:
        # Fallback to naive UTC (prototype)
        return datetime.utcnow()

def _build_feature_frame(session: Session) -> pd.DataFrame:
    """
    Build a per-customer feature frame from ORM entities.
    """
    customers: List[Customer] = session.query(Customer).all()
    rows: List[Dict] = []
    now = _utcnow()

    for c in customers:
        qs: List[Quotation] = sorted(c.quotations, key=lambda q: q.timestamp or now, reverse=True)
        total_quotes = len(qs)
        totals = [q.total_amount or 0.0 for q in qs]
        total_value = float(np.sum(totals)) if totals else 0.0
        avg_value = float(np.mean(totals)) if totals else 0.0
        if qs and qs[0].timestamp:
            # handle naive timestamps (prototype uses utcnow())
            last_ts = qs[0].timestamp
            if last_ts.tzinfo is None:
                # treat as UTC
                delta_days = (now.replace(tzinfo=None) - last_ts).days
            else:
                delta_days = (now - last_ts).days
        else:
            delta_days = 10_000  # essentially very inactive

        rows.append({
            "customer_id": c.id,
            "customer_name": c.name,
            "total_quotes": total_quotes,
            "total_value": round(total_value, 2),
            "avg_value": round(avg_value, 2),
            "days_since_last": int(delta_days),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        # Ensure columns exist
        df = pd.DataFrame(columns=[
            "customer_id","customer_name","total_quotes",
            "total_value","avg_value","days_since_last"
        ])
    return df

def _label_clusters(df: pd.DataFrame, cluster_col: str, k: int) -> pd.Series:
    """
    Heuristic labeling of clusters by sorting clusters on:
    - higher total_value
    - higher total_quotes
    - lower days_since_last (i.e., more recent)
    Produces labels like: High-Value Frequent, Occasional, Dormant/Low.
    """
    # Aggregate stats per cluster
    agg = df.groupby(cluster_col).agg({
        "total_value": "mean",
        "total_quotes": "mean",
        "days_since_last": "mean"
    }).reset_index()

    # Score: weight high value + freq, penalize recency
    agg["score"] = (
        agg["total_value"].rank(method="min") * 0.6 +
        agg["total_quotes"].rank(method="min") * 0.3 +
        (-agg["days_since_last"]).rank(method="min") * 0.1
    )

    # Sort clusters by score descending
    agg = agg.sort_values("score", ascending=False).reset_index(drop=True)

    # Map to friendly labels by rank
    labels = []
    base_labels = ["High-Value Frequent", "Occasional", "Dormant/Low"]
    for i in range(len(agg)):
        labels.append(base_labels[i] if i < len(base_labels) else f"Segment {i+1}")
    label_map = { int(row[cluster_col]): labels[i] for i, row in agg.iterrows() }

    return df[cluster_col].map(label_map)

def compute_customer_segments(session: Session, k: int = 3) -> pd.DataFrame:
    """
    Builds features, clusters customers, returns a DataFrame with features + cluster + label.
    """
    df = _build_feature_frame(session)
    if df.empty:
        return df

    feat_cols = ["total_quotes", "total_value", "avg_value", "days_since_last"]
    X = df[feat_cols].copy()

    # Avoid zero-variance problems
    X = X.fillna(0.0).astype(float)

    # Standardize features
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    # KMeans clustering
    # n_init='auto' for sklearn>=1.4; fall back to 10 for older versions
    try:
        km = KMeans(n_clusters=k, random_state=42, n_init="auto")
    except TypeError:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)

    clusters = km.fit_predict(Xs)
    df["cluster"] = clusters
    df["segment"] = _label_clusters(df, "cluster", k)

    # Useful ordering for presentation
    df = df.sort_values(["segment", "total_value"], ascending=[True, False]).reset_index(drop=True)
    return df[[
        "customer_id", "customer_name", "segment",
        "total_quotes", "total_value", "avg_value", "days_since_last"
    ]]
