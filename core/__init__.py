from flask import Flask, request
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_ckeditor import CKEditor
from flask_googlemaps import GoogleMaps
from flask_wtf import CSRFProtect
from flask_login import LoginManager
from itsdangerous.url_safe import URLSafeTimedSerializer
import os
import sys
import logging
from datetime import date
from time import sleep


# We have our own hacked Gravatar
from core.gravatar_hack import Gravatar


# -------------------------------------------------------------------------------------------------------------- #
# Import env vars if on web server
# -------------------------------------------------------------------------------------------------------------- #

if os.path.exists("/home/ben_freeman_eu/elsr_website/ELSR-Website/env_vars.py"):
    sys.path.insert(1, '/home/ben_freeman_eu/elsr_website/ELSR-Website/')
    import env_vars


# -------------------------------------------------------------------------------------------------------------- #
# Google maps API constants
# -------------------------------------------------------------------------------------------------------------- #

# Note: Key is restricted to IP 195.166.150.111
GOOGLE_MAPS_API_KEY = os.environ['ELSR_GOOGLE_MAPS_API_KEY']

# This is the size and shape of the Google Map insert
MAP_STYLE = "height:500px;width:730px;margin:0;"
# This seems to fit nicely on my iPhone SE 2nd gen
mMAP_STYLE = "height:500px;width:350px;margin:0;"


# -------------------------------------------------------------------------------------------------------------- #
# File upload constants
# -------------------------------------------------------------------------------------------------------------- #

# Flask only seems to allow one global upload folder, but we have two different end folders for GPX files and
# cafe images. So, we upload to the same place and then move the file afterwards to it's final home.
GPX_UPLOAD_FOLDER_ABS = os.environ['ELSR_GPX_UPLOAD_FOLDER_ABS']


# -------------------------------------------------------------------------------------------------------------- #
# Start Flask Framework
# -------------------------------------------------------------------------------------------------------------- #

app = Flask(__name__)

# Details on the Secret Key: https://flask.palletsprojects.com/en/2.3.x/config/#SECRET_KEY
# NOTE: The secret key is used to cryptographically-sign the cookies used for storing the session data.
app.config['SECRET_KEY'] = os.environ['ELSR_FLASK_SECRET_KEY']


# -------------------------------------------------------------------------------------------------------------- #
# Initialise the login manager
# -------------------------------------------------------------------------------------------------------------- #

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.session_protection = "basic"
login_serializer = URLSafeTimedSerializer(app.secret_key)
app.config['REMEMBER_COOKIE_NAME'] = "remember_token"


# -------------------------------------------------------------------------------------------------------------- #
# Set maximum file upload size.
# -------------------------------------------------------------------------------------------------------------- #

# Seems GPX files are massive eg my polar files are often 5 MB, so we need 10 MB as a limit.
# NB We shrink the files down to a few 100 kB afterwards.
app.config['MAX_CONTENT_LENGTH'] = 10 * 1000 * 1000


# -------------------------------------------------------------------------------------------------------------- #
# Configure logging
# -------------------------------------------------------------------------------------------------------------- #

app.logger.setLevel(logging.DEBUG)
app.logger.debug('this will show in the log')


# -------------------------------------------------------------------------------------------------------------- #
# Connect to the different SQLite databases
# -------------------------------------------------------------------------------------------------------------- #

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafes.db'
app.config['SQLALCHEMY_BINDS'] = {'users': 'sqlite:///users.db',
                                  'cafe_comments': 'sqlite:///cafe_comments.db',
                                  'gpx': 'sqlite:///gpx.db',
                                  'messages': 'sqlite:///messages.db',
                                  'events': 'sqlite:///events.db'}
db = SQLAlchemy(app)


# -------------------------------------------------------------------------------------------------------------- #
# Bootstrap Flask
# -------------------------------------------------------------------------------------------------------------- #

Bootstrap(app)


# -------------------------------------------------------------------------------------------------------------- #
# Initialise the Flask CK Editor (gives formatting in the form eg bold etc)
# -------------------------------------------------------------------------------------------------------------- #

ckeditor = CKEditor(app)


# -------------------------------------------------------------------------------------------------------------- #
# Add CSRF protection to flask forms
# -------------------------------------------------------------------------------------------------------------- #

csrf = CSRFProtect(app)


# -------------------------------------------------------------------------------------------------------------- #
# Add Google Maps to Flask app
# -------------------------------------------------------------------------------------------------------------- #

app.config['GOOGLEMAPS_KEY'] = GOOGLE_MAPS_API_KEY
GoogleMaps(app)


# -------------------------------------------------------------------------------------------------------------- #
# Initialise Gravatar util
# -------------------------------------------------------------------------------------------------------------- #

# NB This is our own hacked Gravatar with fake celeb icons
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False,
                    force_lower=False, use_ssl=True, base_url=None)


# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #

# Year for (C)
current_year = date.today().year


# Get map size for desktop / mobile
def dynamic_map_size():
    user_agent_details = request.user_agent.string
    phones = ["iphone", "android", "mobile"]
    if any(phone in user_agent_details.lower() for phone in phones):
        map_style = mMAP_STYLE
        app.logger.debug(f"Detected mobile: '{user_agent_details}'.")
    else:
        map_style = MAP_STYLE
        app.logger.debug(f"Detected desktop: '{user_agent_details}'.")
    return map_style


def delete_file_if_exists(filename):
    if os.path.exists(filename):
        try:
            os.remove(filename)
            # We need this as remove seems to keep the file locked for a short period
            sleep(0.5)
            return True
        except Exception as e:
            app.logger.debug(f"delete_file_if_exists(): Failed to delete existing file '{filename}', "
                             f"error code was '{e.args}'.")
            print(f"delete_file_if_exists(): Failed to delete existing file '{filename}', error code was '{e.args}'.")
            return False
    # If file not there, return True as can continue etc
    return True

