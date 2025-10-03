
# 🏗 Reliant Windows – ERP/CRM Prototype with AI Support

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3%2B-black?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3.40%2B-003B57?logo=sqlite&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-7952B3?logo=bootstrap&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.3%2B-F7931E?logo=scikitlearn&logoColor=white)
![Transformers](https://img.shields.io/badge/Transformers-4.41%2B-FFD21E?logo=huggingface&logoColor=black)
![PyTorch](https://img.shields.io/badge/PyTorch-2.1%2B-EE4C2C?logo=pytorch&logoColor=white)

A compact, end-to-end **ERP/CRM prototype** built for **Reliant Windows**, showcasing:

- A **Flask** web app with a clean **Bootstrap 5** UI  
- **SQLite + SQLAlchemy** data model (Users/Roles, Customers, Products, Quotations)  
- **Role-based access** (Manager vs. Sales)  
- **AI price prediction** using **scikit-learn (Linear Regression)**  
- **AI quote summaries** using **Hugging Face Transformers** with a safe **fallback**  
- Practical CRM/ERP workflows: customer management, quotation creation, and history  

This repo is designed to be **clone → install → run**. Ideal for technical evaluation and a foundation for production.

---

## 📋 Table of Contents
- [Features](#-features)
- [Quick Start](#-quick-start)
- [AI Components](#-ai-components)
- [Screenshots](#-screenshots)
- [Demo Video](#-demo-video)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)

---

## 🚀 Quick Start

> **Requirements**: Python **3.10+** (Python **3.11** recommended). Works on macOS, Linux, Windows.

### Option A — Virtualenv (cross-platform)

```bash
# 1) Clone
git clone <YOUR_REPO_URL>.git
cd erp_crm_prototype

# 2) Create & activate venv
python -m venv venv
# macOS/Linux:
source venv/bin/activate
# Windows (PowerShell):
.env\Scripts\Activate.ps1

# 3) Install dependencies
pip install -U pip
pip install -r requirements.txt

# 4) Initialize the database (also trains the price model)
python seed_database.py

# 5) Run
export FLASK_APP=app.py
export FLASK_ENV=development
python -m flask run
# If port 5000 is busy: python -m flask run --port 5001

```

### Option B — Conda (recommended on Apple Silicon)

```bash
conda create -n reliant-erpcrm -c conda-forge python=3.11 -y
conda activate reliant-erpcrm
# Fast native builds for numpy/pandas/sklearn/torch
conda install -c conda-forge numpy pandas scikit-learn pytorch -y
pip install -U pip
pip install -r requirements.txt

python seed_database.py
python -m flask run

```

Open: **http://127.0.0.1:5000**

**Test Accounts**
- **Manager**: `manager@reliant.com` / `manager123`  
- **Sales**: `sales@reliant.com` / `sales123`

> Notes:
> - The summarizer loads a **small model** (`t5-small`) cached locally. If offline or a model issue occurs, a robust **template fallback** still produces a professional summary.
> - The ML price model is trained from seeded data and stored at `instance/price_model.pkl`.

### (Optional) Preload the HF model once (for instant summaries)

```bash
# Login with your HF token (READ access)
pip install -U huggingface_hub
huggingface-cli login  # paste token

# Keep cache inside the project (optional)
export HF_HOME="$PWD/.hfhome"

# Preload a reliable small model (t5-small)
export SUMMARY_MODEL=t5-small
python preload_models.py
```

---

## 🎯 Features

| Area | Capability |
|---|---|
| 🗂 **CRM** | Create/edit customers (Manager-only), view customers, see quotation history per customer |
| 🧾 **ERP – Quotations** | Create quotations with dynamic items (product, qty, dimensions, unit price), view details & totals |
| 🧠 **AI Support** | Price prediction (scikit-learn Linear Regression); Quote summaries (Transformers with fallback) |
| 🔐 **Auth & Roles** | Session login; **Manager** sees/does everything; **Sales** sees only their quotations; Manager-only customer creation/editing |
| 🧭 **Dashboard** | Recent quotations with **one-click AI summary generate/refresh** |
| 🧱 **Tech Stack** | Flask, SQLAlchemy, Jinja2, Bootstrap 5, SQLite, scikit-learn, Transformers, PyTorch |
| 🧪 **Seed Data** | 30+ quotations across multiple customers & products for realistic demo/training |

---

## 🤖 AI Components

### 1) AI Price Predictor (scikit-learn)
**File**: `price_predictor.py`  
**Model**: `LinearRegression` trained on seeded `QuotationItem` data.

**Features per line item**
- `category` (one-hot encoded)
- `area` = `width_ft * height_ft`
- `quantity`
- `base_cost_per_sqft` (from Product)

**Output**
- Predicts **line totals**; overall suggestion = **sum of predicted line totals**.

**Integration**
- **Endpoint**: `POST /api/predict_price`  
  Request: list of `{product_id, quantity, width_ft, height_ft}`; server enriches with product metadata and returns `suggested_total`.
- **UI**: On **Create Quotation**, click **“Get AI Price Suggestion”** to see a suggested total and optionally apply a uniform unit price.

---

### 2) AI Quote Summary Generator (Transformers + Fallback)
**File**: `summary_generator.py`  
**Default model**: `t5-small` (fast, reliable).  
*Supports any HF summarization model via `SUMMARY_MODEL` env var; adds the `summarize:` prefix automatically for T5-family.*

**How it works**
- Builds structured text (customer, items, categories, dimensions, quantities, total).
- Uses **Transformers** for summarization.
- If loading/inference fails, falls back to a clear, professional **template**—so a summary is always produced.

**Integration**
- Automatically generates and stores `Quotation.ai_summary` **when creating a quotation**.
- **Dashboard** (`/`) includes a **Generate** button per quote to (re)generate summaries via `POST /api/generate_summary`.

---

## 📸 Screenshots

| Feature | Preview |
|--------|---------|
| Login Page | ![Login](outputs/login.png) |
| Manager – Customers | ![Manager Customers](outputs/Customers_manager.png) |
| Create/Edit Customer | ![Customer Form](outputs/customer_form.png) |
| Create Quotation (Form) | ![Quotation Form](outputs/Quotations_Form.png) |
| Quotations List | ![Quotations Page](outputs/Quotations_Page.png) |
| Quotation Detail with AI Summary | ![AI Summary on Detail](outputs/Quotations_view_AI_Customer_Summary.png) |
| **Dashboard – AI Summary Control** | ![AI Summary Dashboard](outputs/AI_SUMMARY_DASHBOARD.png) |
| Workflow Overview | ![Workflow Diagram](outputs/workflow.png) |
|SYSTEM ARCHITECTURE & TECHNICAL DESIGN| ![Workflow Diagram](outputs/SYSTEM_ARCHITECTURE.png) |
> All images live under `outputs/`.

---

## 🎥 Demo Video

**Demo Video:** [Watch Walkthrough](Video_explanation/VideoExplanation.mp4)

(Local file path: `Video_explanation/VideoExplanation.mp4`)

---

## 🧪 API Reference

> The app is primarily server-rendered, with two JSON endpoints for AI.

### `POST /api/predict_price`
**Purpose**: Suggest a total price for current quotation items.

**Request**
```json
{
  "items": [
    {"product_id": 12, "quantity": 2, "width_ft": 4.0, "height_ft": 3.5},
    {"product_id": 7,  "quantity": 1, "width_ft": 6.0, "height_ft": 6.0}
  ]
}
```

**Response**
```json
{ "ok": true, "suggested_total": 4820.75 }
```

---

### `POST /api/generate_summary`
**Purpose**: Generate or refresh the AI summary for a quotation.

**Request**
```json
{ "quotation_id": 101 }
```

**Response**
```json
{
  "ok": true,
  "summary": "This quotation for Alice Smith covers..."
}
```

**Permissions**
- **Manager**: summarize any quotation.
- **Sales**: summarize only their own quotations.

---

## 🏗️ Project Structure

```
erp_crm_prototype/
├── app.py                      # Flask app (routes, RBAC, AI API)
├── models.py                   # SQLAlchemy models
├── price_predictor.py          # scikit-learn model training & inference
├── summary_generator.py        # Transformers summarization with fallback
├── preload_models.py           # Optional: pre-cache HF model (token-aware)
├── seed_database.py            # Create & seed DB; train price model
├── requirements.txt            # Dependencies
├── instance/
│   └── database.db             # SQLite DB (generated)
├── static/
│   └── css/
│       └── custom.css
├── templates/
│   ├── layout.html
│   ├── login.html
│   ├── index.html              # Dashboard with AI summary actions
│   ├── customer_list.html
│   ├── customer_form.html
│   ├── quotation_list.html
│   ├── quotation_form.html     # “Get AI Price Suggestion” button
│   └── quotation_detail.html
├── outputs/                    # Screenshots
│   ├── login.png
│   ├── Customers_manager.png
│   ├── customer_form.png
│   ├── Quotations_Form.png
│   ├── Quotations_Page.png
│   ├── Quotations_view_AI_Customer_Summary.png
│   ├── AI_SUMMARY_DASHBOARD.png
│   └── workflow.png
└── Video_explanation/
    └── overview.mp4
```

---

### 🔐 Roles & Access

- **Manager**
  - View/create/edit customers
  - View all quotations
  - Generate AI summaries for any quote
- **Sales**
  - View customers (read-only in UI)
  - View/create quotations **they own** only
  - Generate AI summaries for **their** quotations

---

### 🛠 Troubleshooting

- **Port 5000 in use**  
  `python -m flask run --port 5001`

- **Model downloads are slow**  
  Use the small model (`t5-small`) and **preload** it:  
  `huggingface-cli login && export SUMMARY_MODEL=t5-small && python preload_models.py`

- **401 Unauthorized from HF**  
  Re-login: `huggingface-cli logout && huggingface-cli login` (READ token).

- **Re-seed database**  
  `python seed_database.py` (drops & recreates tables; retrains price model)

---

**Built for clarity, reliability, and demonstration value — ready to extend into production.**


