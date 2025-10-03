#!/usr/bin/env python3
# app.py
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from models import db, User, Customer, Product, Quotation, QuotationItem
from werkzeug.security import check_password_hash
from price_predictor import predict_quote_total
from summary_generator import generate_quote_summary

def create_app():
    app = Flask(__name__, instance_relative_config=True, static_folder="static", template_folder="templates")
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev-secret-key")
    os.makedirs(app.instance_path, exist_ok=True)
    db_path = os.path.join(app.instance_path, "database.db")
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    # ---------------- Auth ----------------
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email","").strip().lower()
            password = request.form.get("password","")
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                session['role'] = user.role
                session['username'] = user.username
                flash("Logged in successfully.", "success")
                return redirect(url_for("index"))
            flash("Invalid credentials.", "danger")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("Logged out.", "info")
        return redirect(url_for("login"))

    def login_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper

    def role_required(*roles):
        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                if 'user_id' not in session:
                    return redirect(url_for("login"))
                if roles and session.get('role') not in roles:
                    flash("You don't have permission to access that resource.", "warning")
                    return redirect(url_for("index"))
                return f(*args, **kwargs)
            return wrapper
        return decorator

    # ---------------- Home / Dashboard ----------------
    @app.route("/")
    @login_required
    def index():
        # Recent quotations for dashboard (filtered by role)
        if session.get('role') == 'manager':
            quotes = Quotation.query.order_by(Quotation.timestamp.desc()).limit(10).all()
        else:
            quotes = Quotation.query.filter_by(user_id=session.get('user_id')).order_by(Quotation.timestamp.desc()).limit(10).all()
        return render_template("index.html", quotations=quotes)

    # ---------------- CRM: Customers ----------------
    @app.route("/customers")
    @login_required
    def customers():
        customers = Customer.query.order_by(Customer.date_created.desc()).all()
        return render_template("customer_list.html", customers=customers)

    @app.route("/customer/new", methods=["GET","POST"])
    @login_required
    @role_required('manager')   # manager-only
    def customer_new():
        if request.method == "POST":
            name = request.form.get("name")
            email = request.form.get("email")
            phone = request.form.get("phone")
            company_name = request.form.get("company_name")
            address = request.form.get("address")
            if not name:
                flash("Name is required", "danger")
            else:
                c = Customer(name=name, email=email, phone=phone, company_name=company_name, address=address)
                db.session.add(c)
                db.session.commit()
                flash("Customer created.", "success")
                return redirect(url_for("customers"))
        return render_template("customer_form.html", customer=None)

    @app.route("/customer/<int:id>/edit", methods=["GET","POST"])
    @login_required
    @role_required('manager')   # manager-only
    def customer_edit(id):
        customer = Customer.query.get_or_404(id)
        if request.method == "POST":
            customer.name = request.form.get("name")
            customer.email = request.form.get("email")
            customer.phone = request.form.get("phone")
            customer.company_name = request.form.get("company_name")
            customer.address = request.form.get("address")
            db.session.commit()
            flash("Customer updated.", "success")
            return redirect(url_for("customers"))
        return render_template("customer_form.html", customer=customer)

    @app.route("/customer/<int:customer_id>/quotations")
    @login_required
    def customer_quotations(customer_id):
        cust = Customer.query.get_or_404(customer_id)
        if session.get('role') == 'manager':
            quotes = Quotation.query.filter_by(customer_id=customer_id).order_by(Quotation.timestamp.desc()).all()
        else:
            quotes = Quotation.query.filter_by(customer_id=customer_id, user_id=session.get('user_id')).order_by(Quotation.timestamp.desc()).all()
        return render_template("quotation_list.html", quotations=quotes, title=f"Quotations for {cust.name}")

    # ---------------- ERP: Quotations ----------------
    @app.route("/quotations")
    @login_required
    def quotations():
        if session.get('role') == 'manager':
            quotes = Quotation.query.order_by(Quotation.timestamp.desc()).all()
            title = "All Quotations (Manager)"
        else:
            quotes = Quotation.query.filter_by(user_id=session.get('user_id')).order_by(Quotation.timestamp.desc()).all()
            title = "My Quotations"
        return render_template("quotation_list.html", quotations=quotes, title=title)

    @app.route("/quotation/new", methods=["GET","POST"])
    @login_required
    def quotation_new():
        customers = Customer.query.order_by(Customer.name).all()
        products = Product.query.order_by(Product.name).all()
        if request.method == "POST":
            title = request.form.get("title")
            customer_id = request.form.get("customer_id")
            status = request.form.get("status","Draft")

            # Collect items from the dynamic form
            items = []
            idx = 0
            while True:
                pid = request.form.get(f"items[{idx}][product_id]")
                if pid is None:
                    break
                if pid.strip() == "":
                    idx += 1
                    continue
                product = Product.query.get(int(pid))
                quantity = int(request.form.get(f"items[{idx}][quantity]", 1))
                width_ft = float(request.form.get(f"items[{idx}][width_ft]", 0))
                height_ft = float(request.form.get(f"items[{idx}][height_ft]", 0))
                unit_price = float(request.form.get(f"items[{idx}][unit_price]", 0.0))

                area = width_ft * height_ft
                line_total = unit_price * quantity * max(area, 1.0)  # simple baseline calc
                items.append({
                    "product": product,
                    "product_id": product.id,
                    "quantity": quantity,
                    "width_ft": width_ft,
                    "height_ft": height_ft,
                    "unit_price": unit_price,
                    "line_total": line_total
                })
                idx += 1

            total_amount = sum(i['line_total'] for i in items)

            # Create quotation
            q = Quotation(
                title=title,
                customer_id=int(customer_id),
                user_id=session.get('user_id'),
                total_amount=total_amount,
                status=status,
            )
            db.session.add(q)
            db.session.flush()  # get q.id

            # Add items
            for i in items:
                qi = QuotationItem(
                    quotation_id=q.id,
                    product_id=i['product_id'],
                    quantity=i['quantity'],
                    width_ft=i['width_ft'],
                    height_ft=i['height_ft'],
                    unit_price=i['unit_price'],
                    line_total=i['line_total']
                )
                db.session.add(qi)
            db.session.commit()

            # Generate AI summary post-commit so we have items saved
            try:
                items_for_summary = [{
                    "name": i['product'].name,
                    "category": i['product'].category,
                    "quantity": i['quantity'],
                    "width_ft": i['width_ft'],
                    "height_ft": i['height_ft']
                } for i in items]
                customer = Customer.query.get(int(customer_id))
                summary = generate_quote_summary(customer.name, items_for_summary, total_amount)
                q.ai_summary = summary
                db.session.commit()
            except Exception as e:
                print(f"[app] Failed to generate summary: {e}")

            flash("Quotation created.", "success")
            return redirect(url_for("quotation_detail", id=q.id))

        # JSON-serializable product projection for the template JS
        products_js = [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "base_cost_per_sqft": float(p.base_cost_per_sqft),
            }
            for p in products
        ]
        return render_template("quotation_form.html", customers=customers, products_js=products_js)

    @app.route("/quotation/<int:id>")
    @login_required
    def quotation_detail(id):
        q = Quotation.query.get_or_404(id)
        # Permission: sales can only view their own
        if session.get('role') != 'manager' and q.user_id != session.get('user_id'):
            flash("You don't have permission to view that quotation.", "warning")
            return redirect(url_for("quotations"))
        return render_template("quotation_detail.html", q=q)

    # ---------------- AI price suggestion API ----------------
    @app.route("/api/predict_price", methods=["POST"])
    @login_required
    def api_predict_price():
        """
        Expects JSON: {items: [{product_id, quantity, width_ft, height_ft}]}
        """
        try:
            data = request.get_json() or {}
            items = data.get("items", [])
            payload = []
            for it in items:
                product = Product.query.get(int(it["product_id"]))
                if not product:
                    continue
                payload.append({
                    "category": product.category,
                    "width_ft": float(it.get("width_ft", 0)),
                    "height_ft": float(it.get("height_ft", 0)),
                    "quantity": int(it.get("quantity", 1)),
                    "base_cost_per_sqft": float(product.base_cost_per_sqft),
                })
            suggested = predict_quote_total(payload)
            return jsonify({"ok": True, "suggested_total": suggested})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    # ---------------- AI summary (re)generator API for dashboard ----------------
    @app.route("/api/generate_summary", methods=["POST"])
    @login_required
    def api_generate_summary():
        """
        Expects JSON: {quotation_id: int}
        Generates (or refreshes) ai_summary for the given quotation and returns it.
        """
        try:
            data = request.get_json() or {}
            qid = int(data.get("quotation_id"))
        except Exception:
            return jsonify({"ok": False, "error": "Invalid quotation_id"}), 400

        q = Quotation.query.get_or_404(qid)

        # Permission: sales can only act on their own quotations
        if session.get('role') != 'manager' and q.user_id != session.get('user_id'):
            return jsonify({"ok": False, "error": "Permission denied"}), 403

        items_for_summary = [{
            "name": it.product.name,
            "category": it.product.category,
            "quantity": it.quantity,
            "width_ft": it.width_ft,
            "height_ft": it.height_ft
        } for it in q.items]

        try:
            summary = generate_quote_summary(q.customer.name, items_for_summary, q.total_amount)
            q.ai_summary = summary
            db.session.commit()
            return jsonify({"ok": True, "summary": summary})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
