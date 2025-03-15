import json
import os
import random
import uuid

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from google import genai

load_dotenv()

app = Flask(__name__)
app.secret_key = "abc"
DATA_FILE = "database.json"

ai = genai.Client(api_key=os.getenv("GEMINI"))

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"users": [], "items": []}, f, indent=4)


def read_db():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def write_db(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


@app.route("/")
def index():
    user = session.get("user")
    return render_template("homepage.html", user=user)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))

        db = read_db()

        if any(u["username"] == username for u in db["users"]):
            flash("User already exists.")
            return redirect(url_for("register"))

        new_user = {
            "id": str(uuid.uuid4()),
            "username": username,
            "password": password,
            "items": [],
        }
        db["users"].append(new_user)
        write_db(db)
        flash("User registered successfully! Your user ID is: " + new_user["id"])
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        db = read_db()
        user = next(
            (
                u
                for u in db["users"]
                if u["username"] == username and u["password"] == password
            ),
            None,
        )
        if user:
            session["user"] = user  # Store user details in the session.
            flash("Logged in successfully!")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials.")
            return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out.")
    return redirect(url_for("index"))


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file provided.")
            return redirect(url_for("upload"))

        file = request.files["file"]
        # user_id = request.form.get("user_id")
        # if not user_id:
        #     flash("User ID is required.")
        #     return redirect(url_for("upload"))

        os.makedirs("uploads", exist_ok=True)
        file_path = os.path.join("uploads", file.filename)
        print(file)
        file.save(file_path)

        # # Simulate the Gemini 2.0 Flash API processing.
        # simulated_response = {
        #     "name": "chair",
        #     "variety": "old wooden chair",
        #     "rarity": "common",
        #     "hp": 50,
        #     "moves": [
        #         "Slam",
        #         "Rest",
        #         "Scratch"
        #     ]
        # }

        # db = read_db()
        # user = next((u for u in db["users"] if u["id"] == user_id), None)
        # if not user:
        #     flash("User not found.")
        #     return redirect(url_for('upload'))

        # new_item = {
        #     "id": str(uuid.uuid4()),
        #     "owner": user_id,
        #     "data": simulated_response,
        #     "photo": file_path
        # }
        # db["items"].append(new_item)
        # user["items"].append(new_item["id"])
        # write_db(db)

        flash("Item uploaded and processed!")
        return redirect(url_for("index"))

    return render_template("upload.html")


@app.route("/battle")
def battle(): ...


if __name__ == "__main__":
    app.run(debug=True)
