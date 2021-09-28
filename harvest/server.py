from flask import Flask, render_template, request, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import threading
import json

from flask_login import LoginManager, login_user, login_required, logout_user, current_user

from harvest.utils import debugger

class User:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.default_password = True
        self.is_authenticated = False 
        self.is_active = True 
        self.is_anonymous = False
    
    def get_id(self):
        return self.username

class DB:
    
    def __init__(self):
        self.users = []

    def add_user(self, username, password):
        hashed_password = generate_password_hash(password)
        self.users.append(User(username, hashed_password))

    def update_user_password(self, username, password):
        for user in self.users:
            if user.username == username:
                user.password = generate_password_hash(password)
                user.default_password = False
                return True
        return False

    def get_user(self, username):
        for user in self.users:
            if user.username == username:
                return user
        return None


app = Flask(
    __name__, template_folder="gui", static_folder="gui", static_url_path="/"
)

CORS(app)
login_manager = LoginManager()
login_manager.init_app(app)

db = DB()  # Initiate database

trader = None

class Server:
    """
    Runs a web server in a new thread.
    """

    def __init__(self, t):
        app.config['SECRET_KEY'] = 'secret!' # TODO: Generate random secret key
        db.add_user("admin", "admin") # Default user
        trader = t

    def start(self):
        debugger.info("Starting web server")
        server = threading.Thread(
            target=app.run, kwargs={"port": 11111}, daemon=True
        )
        server.start()

@app.route("/api/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("minimal/login.html")

    username = request.json["username"]
    password = request.json["password"]

    user = db.get_user(username)

    # If user has the right credentials, log the user in.
    if user and check_password_hash(user.password, password):
        login_user(user)
        if user.default_password:
            return redirect("/update_password")
        return {"message", "Success"}
    else:
        return {"message", "Failed"}

@app.route("/api/update_password", methods=["GET", "POST"])
@login_required
def update_password():

    if request.method == "GET":
        return render_template("minimal/update_password.html")

    username = request.json["username"]
    cur_password = request.json["cur_password"]
    new_password = request.json["new_password"]

    user = db.get_user(username)

    if not user.default_password and not check_password_hash(
        user.password, cur_password
    ):
        return {"message", "Incorrect password"}    
    
    db.update_user_password(username, new_password)

@app.route("/api/logout", methods=["POST"])
@login_required
def logout():
    username = request.json["username"]
    user = db.get_user(username)
    logout_user(user)

@login_manager.unauthorized_handler
def unauthorized():
    return redirect("/api/login")

@login_manager.user_loader
def load_user(user_id):
    return db.get_user(user_id)

@app.route("/")
def interface():
    return render_template("index.html")

@app.route("/api/crypto_positions")
def crypto_positions():
    return json.dumps(trader.crypto_positions)

