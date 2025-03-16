import io
import json
import os
import random
import uuid

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from google import genai
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
  - The rarity levels should correspond to how common or rare the item is in the real world. Chairs, grass, paper, and rocks are examples of common items. Smartphones, laptops, cones, and construction paper are examples of uncommon items. Robots and snowflakes are examples of rare items. The more unique or specialized the item, the higher the rarity.
- HP based on the rarity (e.g. 50-100 for common, 100-150 for uncommon, 150-200 for rare, 200-250 for epic, 250-300 for legendary)
  - Evaluate the HP based on how rare it is on this spectrum. If its more rare but classified as uncommon, it should have a higher HP than 100.
- 2 moves based on the item name amd element (e.g. chair: Slam, Splinter; juice box: Sip, Crush; laptop: Code, Compile; cookie: Bite, Dunk; sheet of paper: Plane, Fortune Teller)
- 1 move based on the variety (e.g. tall chair: Fall, Climb; orange juice: Citric Acid; macbook: Apple Crunch; chocolate chip: Chocolatey Crumble; blue construction paper: Ninja Star)

Example:
```json
{
    "name": "chair",
    "variety": "old wooden chair",
    "element": "wooden",
    "rarity": "common",
    "hp": 60,
    "moves": [
        {"name": "Scratch", "type": "normal", "power": 30},
        {"name": "Fall", "type": "normal", "power": 40},
        {"name": "Splinter", "type": "wood", "power": 50},
    ]
}
```

However, if you're unable to do it because the image is invalid for this activity, return no JSON.""",
                image,
            ],
        )
        print("Response:", response.text)

        try:
            output = response.text.replace("```json", "").replace("```", "").strip()
            json_obj = json.loads(output)
        except json.JSONDecodeError:
            flash("Invalid image for processing.")
            return redirect(url_for("upload"))

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


def get_best_cards(user_id, top_n=3):
    db = read_db()
    user = next((u for u in db["users"] if u["id"] == user_id), None)
    if not user or not user.get("items"):
        return []

    items = []
    for item_id in user["items"]:
        item = next((i for i in db["items"] if i["id"] == item_id), None)
        if item:
            items.append(item)

    if not items:
        return []

    def card_score(item):
        hp = item["data"]["hp"]
        total_move_power = sum(move["power"] for move in item["data"]["moves"])
        return hp + total_move_power

    sorted_items = sorted(items, key=card_score, reverse=True)

    return sorted_items[:top_n]


# @app.route("/battle", methods=["GET", "POST"])
# def battle():
#     user = session.get("user")
#     if not user:
#         flash("You must be logged in to battle.")
#         return redirect(url_for("login"))
#     if request.method == "POST":
#         # Logged-in user's ID is automatically used.
#         user1_id = user["id"]
#         # Opponent ID is provided manually (or can be extended to selection logic).
#         opponent_id = request.form.get("opponent_id")
#         if not opponent_id:
#             flash("Opponent ID is required.")
#             return redirect(url_for("battle"))
#         # Randomly select a winner as a placeholder.
#         # find the best 3 cards of each player
#         db = read_db()

#         winner = random.choice([user1_id, opponent_id])
#         flash("Battle concluded! Winner: " + winner)
#         return redirect(url_for("index"))

#     return render_template("battle.html", user=user)


@app.route("/battle", methods=["GET", "POST"])
def battle():
    user = session.get("user")
    if not user:
        flash("You must be logged in to battle.")
        return redirect(url_for("login"))

    if request.method == "POST":
        # Logged-in user's ID
        user1_id = user["id"]

        db = read_db()

        # Find all potential opponents (excluding the current user)
        potential_opponents = [u for u in db["users"] if u["id"] != user1_id]

        if not potential_opponents:
            flash("No opponents available to battle!")
            return redirect(url_for("battle"))

        # Select a random opponent
        opponent = random.choice(potential_opponents)
        opponent_id = opponent["id"]

        # Get the best 3 cards for each player
        user_cards = get_best_cards(user1_id, 3)
        opponent_cards = get_best_cards(opponent_id, 3)

        # Check if both players have at least one card
        if not user_cards:
            flash("You don't have any items to battle with!")
            return redirect(url_for("battle"))
        if not opponent_cards:
            flash(
                f"Opponent {opponent['username']} doesn't have any items to battle with!"
            )
            return redirect(url_for("battle"))

        # Simulate battle
        battle_results = simulate_pokemon_style_battle(
            user_cards, opponent_cards, user["username"], opponent["username"]
        )

        return render_template(
            "battle_results.html",
            battle_results=battle_results,
            user=user,
            opponent=opponent,
            user_cards=user_cards,
            opponent_cards=opponent_cards,
        )

    # For GET requests, just show the battle form
    return render_template("battle.html", user=user)


def simulate_pokemon_style_battle(user_cards, opponent_cards, username, opponent_name):
    """
    Simulate a Pokémon-style battle where players use one card at a time,
    only switching when the current card is defeated.
    """
    battle_log = []

    # Clone the cards to avoid modifying the originals
    user_team = user_cards.copy()
    opponent_team = opponent_cards.copy()

    # Track current active cards
    user_current_card_index = 0
    opponent_current_card_index = 0

    # Track current HP for active cards
    user_current_hp = (
        user_team[user_current_card_index]["data"]["hp"] if user_team else 0
    )
    opponent_current_hp = (
        opponent_team[opponent_current_card_index]["data"]["hp"] if opponent_team else 0
    )

    # Keep track of fainted cards
    user_fainted_count = 0
    opponent_fainted_count = 0

    # Start the battle log
    battle_log.append([f"Battle begins! {username} vs {opponent_name}"])
    battle_log[-1].append(
        f"{username} sends out {user_team[user_current_card_index]['data']['name']}!"
    )
    battle_log[-1].append(
        f"{opponent_name} sends out {opponent_team[opponent_current_card_index]['data']['name']}!"
    )

    # Track turns
    turn = 0
    max_turns = 30  # Prevent infinite battles

    # Track which player goes first (alternate starting player for fairness)
    user_goes_first = random.choice([True, False])

    # Begin battle loop
    while (
        user_fainted_count < len(user_team)
        and opponent_fainted_count < len(opponent_team)
        and turn < max_turns
    ):
        turn += 1
        turn_log = [f"Turn {turn}:"]

        # Get references to current cards
        user_card = user_team[user_current_card_index]
        opponent_card = opponent_team[opponent_current_card_index]

        # First player's turn
        if user_goes_first:
            # User attacks
            if user_current_hp > 0:
                user_move = random.choice(user_card["data"]["moves"])
                damage = user_move["power"]
                opponent_current_hp -= damage
                turn_log.append(
                    f"{username}'s {user_card['data']['name']} used {user_move['name']} for {damage} damage!"
                )

                # Check if opponent's card fainted
                if opponent_current_hp <= 0:
                    turn_log.append(
                        f"{opponent_name}'s {opponent_card['data']['name']} fainted!"
                    )
                    opponent_fainted_count += 1

                    # Check if all opponent cards have fainted
                    if opponent_fainted_count >= len(opponent_team):
                        turn_log.append(f"{opponent_name} has no more cards left!")
                        battle_log.append(turn_log)
                        break

                    # Send out next opponent card
                    opponent_current_card_index += 1
                    opponent_card = opponent_team[opponent_current_card_index]
                    opponent_current_hp = opponent_card["data"]["hp"]
                    turn_log.append(
                        f"{opponent_name} sends out {opponent_card['data']['name']}!"
                    )

            # Opponent attacks (if their card is still active)
            if opponent_current_hp > 0:
                opponent_move = random.choice(opponent_card["data"]["moves"])
                damage = opponent_move["power"]
                user_current_hp -= damage
                turn_log.append(
                    f"{opponent_name}'s {opponent_card['data']['name']} used {opponent_move['name']} for {damage} damage!"
                )

                # Check if user's card fainted
                if user_current_hp <= 0:
                    turn_log.append(
                        f"{username}'s {user_card['data']['name']} fainted!"
                    )
                    user_fainted_count += 1

                    # Check if all user cards have fainted
                    if user_fainted_count >= len(user_team):
                        turn_log.append(f"{username} has no more cards left!")
                        battle_log.append(turn_log)
                        break

                    # Send out next user card
                    user_current_card_index += 1
                    user_card = user_team[user_current_card_index]
                    user_current_hp = user_card["data"]["hp"]
                    turn_log.append(
                        f"{username} sends out {user_card['data']['name']}!"
                    )

        # Second player's turn
        else:
            # Opponent attacks
            if opponent_current_hp > 0:
                opponent_move = random.choice(opponent_card["data"]["moves"])
                damage = opponent_move["power"]
                user_current_hp -= damage
                turn_log.append(
                    f"{opponent_name}'s {opponent_card['data']['name']} used {opponent_move['name']} for {damage} damage!"
                )

                # Check if user's card fainted
                if user_current_hp <= 0:
                    turn_log.append(
                        f"{username}'s {user_card['data']['name']} fainted!"
                    )
                    user_fainted_count += 1

                    # Check if all user cards have fainted
                    if user_fainted_count >= len(user_team):
                        turn_log.append(f"{username} has no more cards left!")
                        battle_log.append(turn_log)
                        break

                    # Send out next user card
                    user_current_card_index += 1
                    user_card = user_team[user_current_card_index]
                    user_current_hp = user_card["data"]["hp"]
                    turn_log.append(
                        f"{username} sends out {user_card['data']['name']}!"
                    )

            # User attacks (if their card is still active)
            if user_current_hp > 0:
                user_move = random.choice(user_card["data"]["moves"])
                damage = user_move["power"]
                opponent_current_hp -= damage
                turn_log.append(
                    f"{username}'s {user_card['data']['name']} used {user_move['name']} for {damage} damage!"
                )

                # Check if opponent's card fainted
                if opponent_current_hp <= 0:
                    turn_log.append(
                        f"{opponent_name}'s {opponent_card['data']['name']} fainted!"
                    )
                    opponent_fainted_count += 1

                    # Check if all opponent cards have fainted
                    if opponent_fainted_count >= len(opponent_team):
                        turn_log.append(f"{opponent_name} has no more cards left!")
                        battle_log.append(turn_log)
                        break

                    # Send out next opponent card
                    opponent_current_card_index += 1
                    opponent_card = opponent_team[opponent_current_card_index]
                    opponent_current_hp = opponent_card["data"]["hp"]
                    turn_log.append(
                        f"{opponent_name} sends out {opponent_card['data']['name']}!"
                    )

        # Add the turn log to the battle log
        battle_log.append(turn_log)

        # Alternate who goes first
        user_goes_first = not user_goes_first

    # If we reached max turns, determine winner by remaining cards
    if turn >= max_turns:
        battle_log.append([f"Battle reached the turn limit!"])
        remaining_user_cards = len(user_team) - user_fainted_count
        remaining_opponent_cards = len(opponent_team) - opponent_fainted_count

        if remaining_user_cards > remaining_opponent_cards:
            battle_log[-1].append(f"{username} wins by having more cards remaining!")
            winner = username
        elif remaining_opponent_cards > remaining_user_cards:
            battle_log[-1].append(
                f"{opponent_name} wins by having more cards remaining!"
            )
            winner = opponent_name
        else:
            # If equal number of cards, check HP of current cards
            if user_current_hp > opponent_current_hp:
                battle_log[-1].append(
                    f"{username} wins by having more HP on their current card!"
                )
                winner = username
            elif opponent_current_hp > user_current_hp:
                battle_log[-1].append(
                    f"{opponent_name} wins by having more HP on their current card!"
                )
                winner = opponent_name
            else:
                battle_log[-1].append("The battle ends in a draw!")
                winner = "Draw"
    else:
        # Determine overall winner based on who has cards left
        if user_fainted_count >= len(user_team):
            battle_log.append([f"{opponent_name} wins the battle!"])
            winner = opponent_name
        else:
            battle_log.append([f"{username} wins the battle!"])
            winner = username

    return {
        "battle_log": battle_log,
        "user_fainted": user_fainted_count,
        "opponent_fainted": opponent_fainted_count,
        "overall_winner": winner,
        "user_name": username,
        "opponent_name": opponent_name,
    }


@app.route("/my-items")
def my_items():
    user = session.get("user")
    if not user:
        flash("You must be logged in to view your items.")
        return redirect(url_for("login"))

    db = read_db()
    # get the user
    user_id = user["id"]
    user = next((u for u in db["users"] if u["id"] == user_id), None)

    # Get the user's items
    items = []
    # print("user", user)
    # print("db", db)
    for item_id in user["items"]:
        print("item_id", item_id)
        item = next((i for i in db["items"] if i["id"] == item_id), None)
        if item:
            items.append(item)

    return render_template("gallery.html", items=items, viewing_other=False)


@app.route("/player/<user_id>")
def player_gallery(user_id):
    current_user = session.get("user")
    if not current_user:
        flash("You must be logged in to view other players' items.")
        return redirect(url_for("login"))

    db = read_db()
    # Find the requested user
    owner = next((u for u in db["users"] if u["id"] == user_id), None)
    if not owner:
        flash("Player not found.")
        return redirect(url_for("index"))

    # Get the owner's items
    items = []
    for item_id in owner["items"]:
        item = next((i for i in db["items"] if i["id"] == item_id), None)
        if item:
            items.append(item)

    return render_template(
        "gallery.html",
        items=items,
        viewing_other=True,
        owner_username=owner["username"],
    )


# Add a route to see all players (useful for discovery)
@app.route("/players")
def players():
    user = session.get("user")
    if not user:
        flash("You must be logged in to view players.")
        return redirect(url_for("login"))

    db = read_db()
    players = db["users"]

    return render_template("players.html", players=players, current_user=user)


# return the image
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory("uploads", filename)


# return the battle music
@app.route("/battle_music")
def battle_music():
    return send_from_directory("static", "battle_music.mp3")


if __name__ == "__main__":
    app.run(debug=True)
