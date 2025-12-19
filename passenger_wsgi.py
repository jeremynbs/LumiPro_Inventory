import sys
import os

# 1. Point to your app folder
sys.path.insert(0, os.path.dirname(__file__))

# 2. Point to the virtual environment libraries
sys.path.insert(0, '/home/jerepnkw/virtualenv/lumipro.jeremynbs.org/3.12/lib/python3.12/site-packages')

# 3. Import your app
from app import app as application