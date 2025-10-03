#!/usr/bin/env python3
# seed_database.py
import os, random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from flask import Flask
from models import db, User, Customer, Product, Quotation, QuotationItem
from price_predictor import train_and_save_model

def create_app_for_seed():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    db_path = os.path.join(app.instance_path, "database.db")
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

def seed():
    app = create_app_for_seed()
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Users
        manager = User(username="Manager", email="manager@reliant.com", password_hash=generate_password_hash("manager123"), role="manager")
        sales = User(username="Sales Rep", email="sales@reliant.com", password_hash=generate_password_hash("sales123"), role="sales")
        db.session.add_all([manager, sales])
        db.session.commit()

        # Customers
        first_names = ["Alice","Bob","Carol","David","Eve","Frank","Grace","Hank","Ivy","Jack","Karen","Leo"]
        last_names = ["Smith","Johnson","Williams","Brown","Jones","Miller","Davis","Garcia","Rodriguez","Wilson","Martinez","Anderson"]
        customers = []
        for i in range(12):
            name = f"{random.choice(first_names)} {random.choice(last_names)}"
            c = Customer(
                name=name,
                email=f"{name.split()[0].lower()}.{name.split()[1].lower()}@example.com",
                phone=f"+44 7{random.randint(100000000, 999999999)}",
                company_name=random.choice(["Homeowner", "Reliant Corp", "Window World", "Bright Homes"]),
                address=f"{random.randint(1,200)} High Street, Birmingham, UK",
                date_created=datetime.utcnow() - timedelta(days=random.randint(0, 120))
            )
            customers.append(c)
        db.session.add_all(customers)
        db.session.commit()

        # Products
        categories = [
            "Double-Hung Window",
            "Casement Window",
            "Bay Window",
            "Picture Window",
            "Sliding Door",
            "French Door"
        ]
        products = []
        for cat in categories:
            for i in range(3):
                base = round(random.uniform(20, 55), 2)  # base cost per sqft
                p = Product(
                    name=f"{cat} Model {chr(65+i)}",
                    description=f"High-efficiency {cat.lower()} with low-E glass and sturdy frame.",
                    category=cat,
                    base_cost_per_sqft=base
                )
                products.append(p)
        db.session.add_all(products)
        db.session.commit()

        # Quotations and items
        quotations = []
        for cust in customers:
            for _ in range(random.randint(2, 4)):  # multiple per customer
                owner = random.choice([manager, sales])
                q = Quotation(
                    title=f"{cust.name} - {random.choice(['Replacement', 'Installation', 'Upgrade'])} Quote",
                    customer_id=cust.id,
                    user_id=owner.id,
                    status=random.choice(['Draft','Sent','Accepted']),
                    timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 60))
                )
                db.session.add(q)
                db.session.flush()

                item_count = random.randint(1,3)
                total = 0.0
                for _ in range(item_count):
                    prod = random.choice(products)
                    quantity = random.randint(1, 5)
                    width = round(random.uniform(2.0, 6.0), 2)
                    height = round(random.uniform(2.0, 6.0), 2)
                    area = width * height
                    # baseline unit price derived from base cost per sqft with margin
                    unit_price = round(prod.base_cost_per_sqft * random.uniform(1.5, 2.5), 2)
                    line_total = round(unit_price * quantity * max(area, 1.0), 2)
                    qi = QuotationItem(
                        quotation_id=q.id,
                        product_id=prod.id,
                        quantity=quantity,
                        width_ft=width,
                        height_ft=height,
                        unit_price=unit_price,
                        line_total=line_total
                    )
                    total += line_total
                    db.session.add(qi)
                q.total_amount = round(total, 2)
                quotations.append(q)
        db.session.commit()

        # Train and store the price model based on seeded data
        print("Training price predictor model from seeded data...")
        train_and_save_model()

        print("✔ Database seeded with users, customers, products, quotations, and items.")
        print("Login with:")
        print("  Manager: manager@reliant.com / manager123")
        print("  Sales:   sales@reliant.com / sales123")

if __name__ == "__main__":
    seed()
