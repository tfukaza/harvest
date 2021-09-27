from flask import Flask, render_template, request, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import threading
import json

from flask_login import LoginManager, login_user, login_required, logout_user, current_user

from harvest.utils import debugger

app = Flask(
    __name__, template_folder="gui", static_folder="gui", static_url_path="/"
)

CORS(app)
login_manager = LoginManager()
login_manager.init_app(app)

class Server:
    """
    Runs a web server in a new thread.
    """

    def __init__(self, trader):
        self.trader = trader
        self.db = DB()  # Initiate database
        app.config['SECRET_KEY'] = 'secret!' # TODO: Generate random secret key
        self.db.add_user("admin", "admin") # Default user

    def start(self):
        debugger.info("Starting web server")
        server = threading.Thread(
            target=app.run, kwargs={"port": 11111}, daemon=True
        )
        server.start()

    @app.route("/api/login")
    def login(self, methods=["POST"]):
        username = request.json["username"]
        password = request.json["password"]

        user = self.db.get_user(username)

        # If user has the right credentials, log the user in.
        if user and check_password_hash(user["password"], password):
            login_user(user)
            if user["default_password"]:
                return redirect("/update_password")
            return {"message", "Success"}
        else:
            return {"message", "Failed"}

    @app.route("/api/init_password")
    @login_required
    def update_password(self, methods=["POST"]):
        username = request.json["username"]
        cur_password = request.json["cur_password"]
        new_password = request.json["new_password"]

        user = self.db.get_user(username)

        if not user["default_password"] and not check_password_hash(
            user["password"], cur_password
        ):
            return {"message", "Incorrect password"}    
        
        self.db.update_user_password(username, new_password)

    @app.route("api/logout")
    @login_required
    def logout(self, methods=["POST"]):
        username = request.json["username"]
        user = self.db.get_user(username)
        logout_user(user)
    
    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect("/login")

    @app.route("/")
    def interface(self):
        return render_template("index.html")

    @app.route("/api/crypto_positions")
    def crypto_positions(self):
        return json.dumps(self.trader.crypto_positions)

class User:
    def __init__(self, username):
        self.username = username
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
        self.users.append({
            "username": username, 
            "password": hashed_password,
            "default_password": True
            })

    def update_user_password(self, username, password):
        for user in self.users:
            if user["username"] == username:
                user["password"] = generate_password_hash(password)
                user["default_password"] = False
                return True
        return False

    def get_user(self, username):
        for user in self.users:
            if user["username"] == username:
                return user
        return None
