from flask import Flask, render_template
from flask_cors import CORS
import threading
import json

from harvest.utils import debugger

class Server:
    """
    Runs a web server in a new thread.
    """

    def __init__(self, trader):
        self.app = Flask(
            __name__, template_folder="gui", static_folder="gui", static_url_path="/"
        )
        CORS(self.app)

        self.app.add_url_rule("/", view_func=self.interface)
        self.app.add_url_rule("/api/crypto_positions", view_func=self.crypto_positions)

        self.trader = trader

    def start(self):
        debugger.info("Starting web server")
        server = threading.Thread(
            target=self.app.run, kwargs={"port": 11111}, daemon=True
        )
        server.start()

    def interface(self):
        return render_template("index.html")

    def crypto_positions(self):
        return json.dumps(self.trader.crypto_positions)
