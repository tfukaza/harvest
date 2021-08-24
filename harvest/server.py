from flask import Flask, render_template
import threading 
import logging

class Server:
    """
    Runs a web server in a new thread.
    """

    def __init__(self, trader):
        self.app = Flask(__name__)

        self.app.add_url_rule('/', view_func=self.interface)
        self.app.add_url_rule('/api/crypto_positions', view_func=self.crypto_positions)
        
        self.trader = trader

        self.debugger = logging.getLogger('harvest')
    
    def start(self):
        self.debugger.info("Starting web server")
        server = threading.Thread(target=self.app.run, kwargs={'port':11111}, daemon=True)
        server.start()
        print("Started server")

    def interface(self):
        return render_template('index.html')
     
    def crypto_positions(self):
        return str(self.trader.crypto_positions)
        