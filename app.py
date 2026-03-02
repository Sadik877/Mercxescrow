import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="templates")
app.secret_key = "mercx_super_secret_key"

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mercx.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ========================
# DATABASE MODEL
# ========================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer = db.Column(db.String(100), nullable=False)
    seller = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="Pending")
    
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========================
# ROUTES
# ========================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful. Please login.")
        return redirect(url_for("login"))

    return render_template("register.html")
    
@app.route("/admin")
@login_required
def admin_panel():
    if not current_user.is_admin:
        return "Access Denied"

    transactions = Transaction.query.all()

    output = "<h2>All Transactions</h2>"
    for tx in transactions:
        output += f"""
        <p>
        ID: {tx.id} |
        Buyer: {tx.buyer} |
        Seller: {tx.seller} |
        Amount: ₦{tx.amount} |
        Status: {tx.status}
        </p>
        """

    return output
    
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return f"Welcome {current_user.username} 👑"
    
@app.route("/create_transaction", methods=["GET", "POST"])
@login_required
def create_transaction():
    if request.method == "POST":
        seller = request.form.get("seller")
        amount = request.form.get("amount")

        new_tx = Transaction(
            buyer=current_user.username,
            seller=seller,
            amount=float(amount)
        )

        db.session.add(new_tx)
        db.session.commit()

        return "Transaction Created Successfully 🛡"

    return """
    <h2>Create Transaction</h2>
    <form method="POST">
    Seller Username:<br>
    <input name="seller"><br><br>
    Amount:<br>
    <input name="amount"><br><br>
    <button type="submit">Create</button>
    </form>
    """
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

# ========================
# RUN
# ========================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Create default admin if not exists
        admin = User.query.filter_by(username="mercx").first()
        if not admin:
            hashed_password = generate_password_hash("Mercury@001")
            admin_user = User(username="admin", password=hashed_password, is_admin=True)
            db.session.add(admin_user)
            db.session.commit()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
