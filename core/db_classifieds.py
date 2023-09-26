from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField, FileField
from wtforms.validators import InputRequired, DataRequired
from flask_ckeditor import CKEditorField
import os
import math
from datetime import datetime, timedelta


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes
# -------------------------------------------------------------------------------------------------------------- #



# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Don't change these as they are in the db
BUY = "BUY"
SELL = "SELL"

STATUS_FOR_SALE = "For sale"
STATUS_UNDER_OFFER = "Under offer"
STATUS_SOLD = "Sold"

# Where we store blog photos
CLASSIFIEDS_PHOTO_FOLDER = os.environ['ELSR_CLASSIFIEDS_PHOTO_FOLDER']


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Classifieds Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class Classified(db.Model):
    # We're using multiple dbs with one instance of SQLAlchemy, so have to bind to the right one.
    __bind_key__ = 'classifieds'

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    # Unique index number
    id = db.Column(db.Integer, primary_key=True)

    # Owner
    email = db.Column(db.String(50))

    # Date (as string)
    date = db.Column(db.String(20))

    # Title
    title = db.Column(db.String(50))

    # Type (Buy or Sell)
    buy_sell = db.Column(db.String(10))

    # Category
    category = db.Column(db.String(20))

    # CSV of filenames (no path)
    image_filenames = db.Column(db.Text)

    # Price
    price = db.Column(db.String(20))

    # Details
    details = db.Column(db.Text)

    # Status (for sale, under offer, sold, etc)
    status = db.Column(db.String(20))

    # ---------------------------------------------------------------------------------------------------------- #
    # Functions
    # ---------------------------------------------------------------------------------------------------------- #
    def all(self):
        with app.app_context():
            classifieds = db.session.query(Classified).all()
            return classifieds

    # Optional: this will allow each event object to be identified by its details when printed.
    def __repr__(self):
        return f'<Classified "{self.title}, by {self.email}">'


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

# This seems to be the only one which works?
with app.app_context():
    db.create_all()

