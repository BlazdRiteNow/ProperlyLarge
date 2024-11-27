import sys
import os

# Add your project directory to path
project_home = '/home/kh1rfan08/Properly'
if project_home not in sys.path:
    sys.path.append(project_home)

from app import app as application 