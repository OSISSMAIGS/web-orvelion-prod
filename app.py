import os
import sys

# Memastikan direktori project masuk ke sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orvelion import create_app

# Instance aplikasi Flask
app = create_app()

# Phusion Passenger (cPanel) mencari callable bernama 'application'
application = app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
