from flask import Flask
import threading 
import logging

class Server:
    """
    Runs a web server in a new thread.
    """

    def __init__(self, trader):
        self.app = Flask(__name__)

        self.app.add_url_rule('/crypto_positions', view_func=self.crypto_positions)
        
        self.trader = trader

        self.debugger = logging.getLogger('harvest')
    
    def start(self):
        self.debugger.info("Starting web server")
        print("Starting server")
        server = threading.Thread(target=self.app.run(port=11111), daemon=True)
        server.start()
     
    def crypto_positions(self):
        return str(self.trader.crypto_positions)
        