import os
import sys

# Ambil direktori tempat file ini berada
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# Jika file ini berada di luar folder (misal di folder osissmaigs.com/),
# otomatis tambahkan subfolder web-orvelion-prod ke sys.path
SUBFOLDER = os.path.join(CURRENT_DIR, "web-orvelion-prod")
if os.path.isdir(SUBFOLDER) and SUBFOLDER not in sys.path:
    sys.path.insert(0, SUBFOLDER)

try:
    # Coba import application dari app.py
    from app import app as application
except ImportError:
    # Fallback langsung create_app dari package orvelion
    from orvelion import create_app
    application = create_app()

app = application
