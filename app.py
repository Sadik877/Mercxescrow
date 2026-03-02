import os
from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "mercx_secret_key"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mercx.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("home"))
    return """
    <form method="POST">
    Username:<br><input name="username"><br>
    Password:<br><input name="password"><br>
    <button type="submit">Register</button>
    </form>
    """

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
