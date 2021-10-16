import logging
from flask import Flask, render_template, request, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import threading
import json

from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
    UserMixin,
)

from harvest.utils import debugger


class User(UserMixin):
    def __init__(self, username, password):
        self.id = username
        self.password = password
        self.default_password = True


class DB:
    def __init__(self):
        self.users = []

    def add_user(self, username, password):
        hashed_password = generate_password_hash(password)
        self.users.append(User(username, hashed_password))

    def update_user_password(self, username, password):
        for user in self.users:
            if user.get_id() == username:
                user.password = generate_password_hash(password)
                user.default_password = False
                return True
        return False

    def set_is_default_password(self, username, is_default):
        for user in self.users:
            if user.get_id() == username:
                user.default_password = is_default

    def get_user(self, username):
        for user in self.users:
            if user.get_id() == username:
                return user
        return None


app = Flask(__name__, template_folder="gui", static_folder="gui", static_url_path="/")

# CORS(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

db = DB()  # Initiate database

trader = None


class Server:
    """
    Runs a web server in a new thread.
    """

    def __init__(self, t):
        app.config["SECRET_KEY"] = "secret!"  # TODO: Generate random secret key
        db.add_user("admin", "admin")  # Default user
        global trader
        trader = t

    def start(self):
        debugger.info("Starting web server")
        server = threading.Thread(target=app.run, kwargs={"port": 11111}, daemon=True)
        server.start()


# ========= Backend API endpoints =========


@app.route("/api/login", methods=["POST"])
def api_login():

    username = request.json["username"]
    password = request.json["password"]

    user = db.get_user(username)

    # If user has the right credentials, log the user in.
    if user and check_password_hash(user.password, password):
        login_user(user)
        if user.default_password:
            return redirect("/update_password")
        else:
            return redirect("/")
    else:
        return redirect("/login")


@app.route("/api/update_password", methods=["POST"])
@login_required
def api_update_password():

    username = current_user.get_id()
    new_password = request.json["password"]

    db.update_user_password(username, new_password)
    db.set_is_default_password(username, False)

    logout_user()
    return redirect("/login")


@app.route("/api/logout", methods=["POST"])
@login_required
def api_logout():
    username = current_user.get_id()
    user = db.get_user(username)
    logout_user(user)


@app.route("/api/crypto_positions")
@login_required
def api_crypto_positions():
    return json.dumps(trader.crypto_positions)


@app.route("/api/stock_positions")
@login_required
def api_stock_positions():
    return json.dumps(trader.stock_positions)


@app.route("/api/option_positions")
@login_required
def api_option_positions():
    return json.dumps(trader.option_positions)


# ========= Web GUI endpoints =========


@app.route("/")
@login_required
def interface():
    return render_template("index.html")


@app.route("/login", methods=["GET"])
def login():
    return render_template("minimal/login.html")


@app.route("/update_password", methods=["GET"])
@login_required
def update_password():
    return render_template("minimal/update_password.html")


# ========= Handlers =========


@login_manager.unauthorized_handler
def unauthorized():
    print("Need to log in")
    return json.dumps({"message": "need to log in"})


@login_manager.user_loader
def load_user(user_id):
    print(user_id)
    u = db.get_user(user_id)
    print(f"got {u.is_authenticated}")
    return u
