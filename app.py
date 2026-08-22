import sys
import os

# Make sure the root folder (where all the modules live) is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Execute the real application on every Streamlit rerun. A normal import is
# cached by Python, which would make login and sidebar interactions render blank.
import runpy
runpy.run_module("quest_app.main", run_name="__main__")
