from flask import Flask
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

# Definitely need this, Nginx / Gunicorn won't load with it.
# Not after changing "current_app." to "app."
#app.app_context().push()

# Details on the Secret Key: https://flask.palletsprojects.com/en/2.3.x/config/#SECRET_KEY
# NOTE: The secret key is used to cryptographically-sign the cookies used for storing the session data.
with app.app_context():
    app.config['SECRET_KEY'] = os.environ['ELSR_FLASK_SECRET_KEY']


# -------------------------------------------------------------------------------------------------------------- #
# Initialise the login manager
# -------------------------------------------------------------------------------------------------------------- #

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.session_protection = "basic"
login_serializer = URLSafeTimedSerializer(app.secret_key)
with app.app_context():
    app.config['REMEMBER_COOKIE_NAME'] = "remember_token"


# -------------------------------------------------------------------------------------------------------------- #
# Set maximum file upload size.
# -------------------------------------------------------------------------------------------------------------- #

# Seems GPX files are massive eg my polar files are often 5 MB, so we need 10 MB as a limit.
# NB We shrink the files down to a few 100 kB afterwards.
with app.app_context():
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1000 * 1000


# -------------------------------------------------------------------------------------------------------------- #
# Add logging for Gunicorn
# -------------------------------------------------------------------------------------------------------------- #

# NB from: https://stackoverflow.com/questions/26578733/why-is-flask-application-not-creating-any-logs-when-hosted-by-gunicorn
with app.app_context():
    gunicorn_error_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers.extend(gunicorn_error_logger.handlers)
    app.logger.setLevel(logging.DEBUG)
    app.logger.debug('this will show in the log')


# -------------------------------------------------------------------------------------------------------------- #
# Connect to the different SQLite databases
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
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

with app.app_context():
    Bootstrap(app)


# -------------------------------------------------------------------------------------------------------------- #
# Initialise the Flask CK Editor (gives formatting in the form eg bold etc)
# -------------------------------------------------------------------------------------------------------------- #


with app.app_context():
    ckeditor = CKEditor(app)


# -------------------------------------------------------------------------------------------------------------- #
# Add CSRF protection to flask forms
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    csrf = CSRFProtect(app)


# -------------------------------------------------------------------------------------------------------------- #
# Add Google Maps to Flask app
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    app.config['GOOGLEMAPS_KEY'] = GOOGLE_MAPS_API_KEY
    GoogleMaps(app)


# -------------------------------------------------------------------------------------------------------------- #
# Initialise Gravatar util
# -------------------------------------------------------------------------------------------------------------- #

# NB This is our own hacked Gravatar with fake celeb icons
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False,
                    force_lower=False, use_ssl=False, base_url=None)

