from flask import Flask, request
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_ckeditor import CKEditor
from flask_wtf import CSRFProtect
from flask_login import LoginManager
from itsdangerous.url_safe import URLSafeTimedSerializer
from sqlalchemy import event
from sqlalchemy.pool import Pool
import os
import sys
import logging
from datetime import date
from time import sleep
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
import psycopg2

# We have our own hacked Gravatar module
from core.gravatar_hack import Gravatar


# -------------------------------------------------------------------------------------------------------------- #
# Useful to know if this is the live site or not
# -------------------------------------------------------------------------------------------------------------- #

def live_site():
    return os.path.exists("/home/ben_freeman_eu/elsr_website/ELSR-Website/env_vars.py")


# -------------------------------------------------------------------------------------------------------------- #
# Import env vars if on live web server (test site uses Pycharm Env Vars)
# -------------------------------------------------------------------------------------------------------------- #

if live_site():
    sys.path.insert(1, '/home/ben_freeman_eu/elsr_website/ELSR-Website/')
    import env_vars


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# These are our standard groups
TWR_CHOICE = "TWR"
GRAVEL_CHOICE = "Gravel"
DECAFF_GROUP = "Decaff"
ESPRESSO_GROUP = "Espresso"
DOPPIO_GROUP = "Doppio"
MIXED_GROUP = "Mixed"
CORTADO_GROUP = "Cortado"
GROUP_CHOICES = [DECAFF_GROUP, ESPRESSO_GROUP, DOPPIO_GROUP, MIXED_GROUP, GRAVEL_CHOICE, TWR_CHOICE, CORTADO_GROUP]

# This set must match the order of GROUP_CHOICES above
GROUP_NOTIFICATIONS = ["When someone posts a Decaff ride",
                       "When someone posts an Espresso ride",
                       "When someone posts a Doppio ride",
                       "When someone posts a Mixed ride",
                       "When someone posts a Gravel ride",
                       "When someone posts a TWR ride"]

# Global Flash Message
GLOBAL_FLASH = None


# -------------------------------------------------------------------------------------------------------------- #
# File upload constants
# -------------------------------------------------------------------------------------------------------------- #

# Flask only seems to allow one global upload folder, but we have two different end folders for GPX files and
# cafe images. So, we upload to the same place and then move the file afterward to its final home.
GPX_UPLOAD_FOLDER_ABS = os.environ['ELSR_GPX_UPLOAD_FOLDER_ABS']


# -------------------------------------------------------------------------------------------------------------- #
# Initialise Sentry (only for live site)
# -------------------------------------------------------------------------------------------------------------- #

dsn = os.environ.get('ELSR_SENTRY_DSN', None)

if dsn:
    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FlaskIntegration(),
        ],

        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0
    )


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

# Seems GPX files are massive eg my polar files are often 5 MB, so we need 15 MB as a limit.
# NB We shrink the files down to a few 100 kB afterwards.
app.config['MAX_CONTENT_LENGTH'] = 15 * 1000 * 1000


# -------------------------------------------------------------------------------------------------------------- #
# Configure logging
# -------------------------------------------------------------------------------------------------------------- #

app.logger.setLevel(logging.DEBUG)


if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(logging.DEBUG)

app.logger.debug('***********************************************************************')
app.logger.debug('***********************************************************************')
app.logger.debug('*                         Logging is working!                         *')
app.logger.debug('***********************************************************************')
app.logger.debug('***********************************************************************')


# -------------------------------------------------------------------------------------------------------------- #
# Connect to the different SQLite databases
# -------------------------------------------------------------------------------------------------------------- #

# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafes.db'
# app.config['SQLALCHEMY_BINDS'] = {'users': 'sqlite:///users.db',
#                                   'cafe_comments': 'sqlite:///cafe_comments.db',
#                                   'gpx': 'sqlite:///gpx.db',
#                                   'messages': 'sqlite:///messages.db',
#                                   'events': 'sqlite:///events.db',
#                                   'calendar': 'sqlite:///calendar.db',
#                                   'socials': 'sqlite:///socials.db',
#                                   'blog': 'sqlite:///blog.db',
#                                   'classifieds': 'sqlite:///classifieds.db',
#                                   'polls': 'sqlite:///polls.db'}


# -------------------------------------------------------------------------------------------------------------- #
# Connect to the single SQLite database
# -------------------------------------------------------------------------------------------------------------- #

# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///elsr_db.db'
# db = SQLAlchemy(app)

# -------------------------------------------------------------------------------------------------------------- #
# Connect to the PostgreSQL database
# -------------------------------------------------------------------------------------------------------------- #

db_host = os.environ.get('ELSR_DB_HOST', 'unset')
db_user = os.environ.get('ELSR_DB_DB_USER', 'unset')
db_pass = os.environ.get('ELSR_DB_DB_PASS', 'unset')
db_name = os.environ.get('ELSR_DB_DB_NAME', 'unset')
db_port = int(os.environ.get('ELSR_DB_PORT', '5432'))

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}'.format(
    db_user=db_user, db_pass=db_pass, db_host=db_host, db_port=db_port, db_name=db_name)

# Custom engine options
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle':  3600,
    'pool_size':     10,
    'max_overflow':  5,
}

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


def is_mobile():
    user_agent_details = request.user_agent.string
    phones = ["iphone", "android", "mobile"]
    if any(phone in user_agent_details.lower() for phone in phones):
        return True
    return False


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


def user_ip():
    # Get user's IP
    if request.headers.getlist("X-Forwarded-For"):
        users_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        users_ip = request.remote_addr
    return users_ip