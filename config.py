import os

# Get the absolute path of the directory where this file resides
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-hard-to-guess-string'
    # Use an absolute path for the SQLite database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'parking_app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Add any other configuration variables if needed