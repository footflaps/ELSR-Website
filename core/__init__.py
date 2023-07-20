from flask import Flask
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_ckeditor import CKEditor
from flask_googlemaps import GoogleMaps
import os

# We have our own hacked Gravatar
from core.gravatar_hack import Gravatar


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
GPX_UPLOAD_FOLDER_ABS = 'D:/Dropbox/100 Days of Code/Python/ELSR-website/core/static/gpx'


# -------------------------------------------------------------------------------------------------------------- #
# Start Flask Framework
# -------------------------------------------------------------------------------------------------------------- #

app = Flask(__name__)

# Unsure if this is still needed...
app.app_context().push()

# Details on the Secret Key: https://flask.palletsprojects.com/en/2.3.x/config/#SECRET_KEY
# NOTE: The secret key is used to cryptographically-sign the cookies used for storing
#       the session data.
app.config['SECRET_KEY'] = os.environ['ELSR_FLASK_SECRET_KEY']

# Set maximum file upload size.
# Seems GPX files are massive eg my polar files are often 5 MB, so we need 10 MB as a limit.
# NB We shrink the files down to a few 100 kB afterwards.
app.config['MAX_CONTENT_LENGTH'] = 10 * 1000 * 1000

# Give the Flask cookie a helpful name
app.config['REMEMBER_COOKIE_NAME'] = "elsr_remember_me"


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
# Add Google Maps to Flask app
# -------------------------------------------------------------------------------------------------------------- #

app.config['GOOGLEMAPS_KEY'] = GOOGLE_MAPS_API_KEY
GoogleMaps(app)


# -------------------------------------------------------------------------------------------------------------- #
# Initialise Gravatar util
# -------------------------------------------------------------------------------------------------------------- #

# NB This is our own hacked Gravatar with fake celeb icons
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False,
                    force_lower=False, use_ssl=False, base_url=None)

