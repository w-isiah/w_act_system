import os
from flask import Flask
from apps import create_app
from apps.config import Config
from flask_cors import CORS

# Create Flask app using factory pattern
app = create_app(Config)

# Enable CORS on the app
CORS(app)

def run_flask():
    """Run Flask app."""
    app.run(debug=app.config['DEBUG'], use_reloader=False)

if __name__ == "__main__":
    run_flask()
