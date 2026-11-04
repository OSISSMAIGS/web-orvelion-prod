import sys
import os

# Menambahkan direktori project ke sys.path
sys.path.insert(0, os.path.dirname(__file__))

# Phusion Passenger (cPanel) mencari callable bernama 'application'
from app import app as application
