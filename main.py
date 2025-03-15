import io
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
from google.genai import types
from PIL import Image

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


def process_uploaded_image(uploaded_file, output_filename=None, resize_dimensions=None):
    try:
        # Validate the file
        if not uploaded_file or uploaded_file.filename == "":
            return {"error": "No file selected"}
        if not uploaded_file.content_type.startswith("image/"):
            return {"error": "Only image files are allowed"}

        # Read the file content into a BytesIO buffer
        buffer = io.BytesIO()
        uploaded_file.save(buffer)
        buffer.seek(0)

        # Open the image using PIL
        img = Image.open(buffer)

        # Resize the image if dimensions are provided
        if resize_dimensions:
            img = img.resize(resize_dimensions)

        # Save the processed image
        # img.save(output_filename)

        # return {"message": "Image processed successfully"}
        return img

    except Exception as e:
        return {"error": str(e)}


@app.route("/upload", methods=["GET", "POST"])
def upload():
    user = session.get("user")
    if not user:
        flash("You must be logged in to upload an item.")
        return redirect(url_for("login"))
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file provided.")
            return redirect(url_for("upload"))
        file = request.files["file"]
        os.makedirs("uploads", exist_ok=True)
        file_id = str(uuid.uuid4())
        file_extension = file.filename.split(".")[-1]
        file_local_path = file_id + "." + file_extension
        file_path = os.path.join("uploads", file_local_path)
        file.save(file_path)

        image = Image.open(file_path)

        # # Simulate the Gemini 2.0 Flash API processing.
        simulated_response = {
            "name": "chair",
            "variety": "old wooden chair",
            "rarity": "common",
            "hp": 50,
            "moves": ["Slam", "Rest", "Scratch"],
        }
        print("image", image)
        response = ai.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                """Process the following image and output only JSON (no ``` necessary) with the following structure:

- Name (e.g. chair, juice box, laptop, cookie, sheet of paper)
- Variety (e.g. tall chair, orange juice, macbook, chocolate chip, blue construction paper)
- Element (e.g. wood, plastic, organic, metal, digital, etc.)
- Rarity (e.g. common, uncommon, rare, epic, legendary)
- HP based on the rarity (e.g. 50 for common, 100 for uncommon, 150 for rare, 200 for epic, 250 for legendary)
- 2 moves based on the item name amd element (e.g. chair: Slam, Splinter; juice box: Sip, Crush; laptop: Code, Compile; cookie: Bite, Dunk; sheet of paper: Plane, Fortune Teller)
- 1 move based on the variety (e.g. tall chair: Fall, Climb; orange juice: Citric Acid; macbook: Apple Crunch; chocolate chip: Chocolatey Crumble; blue construction paper: Ninja Star)

Example:
```json
{
    "name": "chair",
    "variety": "old wooden chair",
    "element": "wooden",
    "rarity": "common",
    "hp": 50,
    "moves": [
        {"name": "Scratch", "type": "normal", "power": 30},
        {"name": "Fall", "type": "normal", "power": 40},
        {"name": "Splinter", "type": "wood", "power": 50},
    ]
}
```""",
                image,
            ],
        )
        print("Response:", response.text)

        output = response.text.replace("```json", "").replace("```", "").strip()
        json_obj = json.loads(output)

        print(response.text)

        db = read_db()
        # Find the logged-in user in the database.
        db_user = next((u for u in db["users"] if u["id"] == user["id"]), None)
        if not db_user:
            flash("User not found.")
            return redirect(url_for("upload"))
        new_item = {
            "id": str(uuid.uuid4()),
            "owner": user["id"],
            "data": json_obj,
            "photo": file_path,
        }
        db["items"].append(new_item)
        db_user["items"].append(new_item["id"])
        write_db(db)

        flash("Item uploaded and processed!")
        return redirect(url_for("index"))
    return render_template("upload.html")


@app.route("/battle", methods=["GET", "POST"])
def battle():
    user = session.get("user")
    if not user:
        flash("You must be logged in to battle.")
        return redirect(url_for("login"))
    if request.method == "POST":
        # Logged-in user's ID is automatically used.
        user1_id = user["id"]
        # Opponent ID is provided manually (or can be extended to selection logic).
        opponent_id = request.form.get("opponent_id")
        if not opponent_id:
            flash("Opponent ID is required.")
            return redirect(url_for("battle"))
        # Randomly select a winner as a placeholder.
        winner = random.choice([user1_id, opponent_id])
        flash("Battle concluded! Winner: " + winner)
        return redirect(url_for("index"))
    return render_template("battle.html", user=user)


if __name__ == "__main__":
    app.run(debug=True)
    app.run(debug=True)
