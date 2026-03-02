import os
import secrets
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "fallback_secret")

# =========================
# DATABASE CONFIG
# =========================

database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mercx.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# EMAIL CONFIG
# =========================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")

mail = Mail(app)

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
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(200), nullable=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer = db.Column(db.String(100), nullable=False)
    seller = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="Pending")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return render_template("index.html")
    
@app.route("/initdb")
def initdb():
    db.create_all()
    return "Database tables created!"
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

        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            return render_template("register.html", error="Username or Email already exists")

        hashed_password = generate_password_hash(password)
        token = secrets.token_hex(16)

        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            verification_token=token
        )

        db.session.add(new_user)
        db.session.commit()

        # Send verification email
        verify_link = url_for("verify_email", token=token, _external=True)

        msg = Message(
            "Verify Your MERCX Account",
            sender=app.config["MAIL_USERNAME"],
            recipients=[email]
        )
        msg.body = f"Click the link to verify your account:\n{verify_link}"

        mail.send(msg)

        return "Check your email to verify your account."

    return render_template("register.html")

# =========================
# EMAIL VERIFY
# =========================

@app.route("/verify/<token>")
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()

    if not user:
        return "Invalid or expired verification link"

    user.is_verified = True
    user.verification_token = None
    db.session.commit()

    return "Your account has been verified. You can now login."

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

            if not user.is_verified:
                return render_template("login.html", error="Please verify your email first.")

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
    transactions = Transaction.query.filter_by(buyer=current_user.username).all()
    total_amount = sum(tx.amount for tx in transactions)

    return render_template(
        "dashboard.html",
        user=current_user,
        transactions=transactions,
        total_amount=total_amount
    )

# =========================
# LOGOUT
# =========================

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

# =========================
# CREATE TABLES
# =========================

with app.app_context():
    db.create_all()

    admin = User.query.filter_by(username="admin").first()
    if not admin:
        hashed_password = generate_password_hash("Mercury@001")
        admin_user = User(
            username="admin",
            email="admin@mercx.site",
            password=hashed_password,
            is_admin=True,
            is_verified=True
        )
        db.session.add(admin_user)
        db.session.commit()

# =========================
# RUN LOCAL
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
