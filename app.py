import os
import pyotp
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from flask_talisman import Talisman
from sqlalchemy import or_

# =========================
# APP CONFIG
# =========================

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "supersecretkey")
app.config["SECURITY_PASSWORD_SALT"] = "mercx_salt"

Talisman(app)

# =========================
# DATABASE CONFIG
# =========================

database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    if "sslmode=" not in database_url:
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

serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

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
    otp_secret = db.Column(db.String(32), nullable=False, default=lambda: pyotp.random_base32())

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer = db.Column(db.String(100), nullable=False)
    seller = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="Created")
    buyer_paid = db.Column(db.Boolean, default=False)
    seller_confirmed = db.Column(db.Boolean, default=False)
    released = db.Column(db.Boolean, default=False)

class LoginActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    ip_address = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# =========================
# PASSWORD RESET
# =========================

def generate_reset_token(email):
    return serializer.dumps(email, salt=app.config["SECURITY_PASSWORD_SALT"])

def confirm_reset_token(token, expiration=3600):
    try:
        email = serializer.loads(
            token,
            salt=app.config["SECURITY_PASSWORD_SALT"],
            max_age=expiration
        )
    except Exception:
        return None
    return email

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return render_template("index.html")

# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            return render_template("register.html", error="All fields required")

        existing_user = User.query.filter(
            or_(User.username == username, User.email == email)
        ).first()

        if existing_user:
            return render_template("register.html", error="User already exists")

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            otp_secret=pyotp.random_base32()
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

# LOGIN STEP 1
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        remember = True if request.form.get("remember") else False

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session["pre_2fa_user"] = user.id
            session["remember_me"] = remember
            return redirect(url_for("verify_otp"))

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

# OTP VERIFY
@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    user_id = session.get("pre_2fa_user")
    if not user_id:
        return redirect(url_for("login"))

    user = db.session.get(User, user_id)
    totp = pyotp.TOTP(user.otp_secret)

    if request.method == "POST":
        otp = request.form.get("otp")

        if totp.verify(otp):
            remember = session.get("remember_me", False)
            login_user(user, remember=remember)

            session.pop("pre_2fa_user", None)
            session.pop("remember_me", None)

            activity = LoginActivity(
                username=user.username,
                ip_address=request.remote_addr
            )
            db.session.add(activity)
            db.session.commit()

            return redirect(url_for("dashboard"))

        return render_template("verify.html", error="Invalid OTP")

    return render_template("verify.html")

# DASHBOARD
@app.route("/dashboard")
@login_required
def dashboard():
    transactions = Transaction.query.filter(
        or_(
            Transaction.buyer == current_user.username,
            Transaction.seller == current_user.username
        )
    ).all()

    return render_template("dashboard.html", user=current_user, transactions=transactions)

# FORGOT PASSWORD
@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()

        if user:
            token = generate_reset_token(user.email)
            reset_link = url_for("reset_password", token=token, _external=True)
            print("RESET LINK:", reset_link)

        return render_template("forgot.html", message="If email exists, reset link sent.")

    return render_template("forgot.html")

# RESET PASSWORD
@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = confirm_reset_token(token)
    if not email:
        return "Invalid or expired token"

    if request.method == "POST":
        new_password = request.form.get("password")
        user = User.query.filter_by(email=email).first()

        user.password = generate_password_hash(new_password)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("reset.html")

# LOGOUT
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
            is_admin=True,
            otp_secret=pyotp.random_base32()
        )
        db.session.add(admin_user)
        db.session.commit()

# =========================

if __name__ == "__main__":
    app.run(debug=True)
