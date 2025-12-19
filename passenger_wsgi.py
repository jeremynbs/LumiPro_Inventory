import sys
import os

# 1. Point to your app folder
sys.path.insert(0, os.path.dirname(__file__))

# 2. Point to the virtual environment libraries
# Replace 'jerepnkw' with your username and '3.10' with your version
sys.path.insert(0, '/home/jerepnkw/virtualenv/repositories/LumiPro_Inventory/3.13/lib/python3.13/site-packages')

# 3. Import your app
from app import app as application