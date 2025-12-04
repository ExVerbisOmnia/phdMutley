
import sys
import os
from flask import Flask, render_template

# Add railway directory to path so we can import if needed, 
# but here we just want to test rendering.
# We need to point Flask to the correct template folder.
template_dir = os.path.abspath('railway/templates')
app = Flask(__name__, template_folder=template_dir)

@app.route('/')
def index():
    try:
        return render_template('dashboard.html')
    except Exception as e:
        return f"Error: {e}", 500

if __name__ == '__main__':
    print(f"Template folder: {template_dir}")
    with app.app_context():
        try:
            rendered = render_template('dashboard.html')
            print("Successfully rendered dashboard.html")
            print(f"Length: {len(rendered)}")
        except Exception as e:
            print(f"Failed to render dashboard.html: {e}")
            sys.exit(1)
