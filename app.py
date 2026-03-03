import os
from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# =========================
# APP CONFIG
# =========================

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "supersecretkey")

# =========================
# DATABASE CONFIG (RENDER SAFE)
# =========================

database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    if "sslmode=" not in database_url:
        if "?" in database_url:
            database_url += "&sslmode=require"
        else:
            database_url += "?sslmode=require"

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mercx.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# LOGIN CONFIG
# =========================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# =========================
# MODELS
# =========================

class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer = db.Column(db.String(100), nullable=False)
    seller = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    status = db.Column(db.String(50), default="Created")
    buyer_paid = db.Column(db.Boolean, default=False)
    seller_confirmed = db.Column(db.Boolean, default=False)
    released = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match")

        if User.query.filter((User.username == username) | (User.email == email)).first():
            return render_template("register.html", error="Username or Email already exists")

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
@login_required
def dashboard():
    transactions = Transaction.query.filter(
        (Transaction.buyer == current_user.username) |
        (Transaction.seller == current_user.username)
    ).all()

    return render_template(
        "dashboard.html",
        user=current_user,
        transactions=transactions
    )

# =========================
# CREATE TRANSACTION
# =========================

@app.route("/create", methods=["GET", "POST"])
@login_required
def create_transaction():
    if request.method == "POST":
        seller = request.form.get("seller")
        amount = float(request.form.get("amount"))

        new_tx = Transaction(
            buyer=current_user.username,
            seller=seller,
            amount=amount
        )

        db.session.add(new_tx)
        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("create.html")

# =========================
# MARK AS PAID (BUYER)
# =========================

@app.route("/pay/<int:tx_id>")
@login_required
def mark_paid(tx_id):
    tx = Transaction.query.get_or_404(tx_id)

    if tx.buyer == current_user.username and not tx.buyer_paid:
        tx.buyer_paid = True
        tx.status = "Paid"
        db.session.commit()

    return redirect(url_for("dashboard"))

# =========================
# CONFIRM DELIVERY (SELLER)
# =========================

@app.route("/confirm/<int:tx_id>")
@login_required
def confirm_delivery(tx_id):
    tx = Transaction.query.get_or_404(tx_id)

    if tx.seller == current_user.username and tx.buyer_paid:
        tx.seller_confirmed = True
        tx.status = "Delivered"
        db.session.commit()

    return redirect(url_for("dashboard"))

# =========================
# RELEASE FUNDS (ADMIN)
# =========================

@app.route("/release/<int:tx_id>")
@login_required
def release_funds(tx_id):
    tx = Transaction.query.get_or_404(tx_id)

    if current_user.is_admin and tx.seller_confirmed:
        tx.released = True
        tx.status = "Released"
        db.session.commit()

    return redirect(url_for("dashboard"))

# =========================
# LOGOUT
# =========================

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

# =========================
# INITIAL SETUP
# =========================

with app.app_context():
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin_user = User(
            username="admin",
            email="admin@mercx.site",
            password=generate_password_hash("Mercury@001"),
            is_admin=True
        )
        db.session.add(admin_user)
        db.session.commit()
