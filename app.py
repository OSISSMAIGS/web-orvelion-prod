import os

from orvelion import create_app

app = create_app()

if __name__ == "__main__":
    # Default tetap aktif untuk development (auto-reload). Set FLASK_DEBUG=0
    # saat menjalankan di lingkungan production supaya debugger Werkzeug mati.
    app.run(host="127.0.0.1", port=5000, debug=os.environ.get("FLASK_DEBUG", "1") != "0")
