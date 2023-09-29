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
SELL = "FS"

STATUS_FOR_SALE = "For sale"
STATUS_UNDER_OFFER = "Under offer"
STATUS_SOLD = "Sold"

STATUSES = [STATUS_FOR_SALE,
            STATUS_UNDER_OFFER,
            STATUS_SOLD]

# Where we store blog photos
CLASSIFIEDS_PHOTO_FOLDER = os.environ['ELSR_CLASSIFIEDS_PHOTO_FOLDER']

CATEGORIES = ["Complete bikes",
              "Wheels",
              "Bike parts",
              "Bike tools",
              "Clothing",
              "Accessories",
              "Other"]

# Cap how many photos they can have
MAX_NUM_PHOTOS = 5

DELETE_PHOTO = "Delete"
DEL_IMAGE = ["Keep",
             DELETE_PHOTO]

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
    # Properties
    # ---------------------------------------------------------------------------------------------------------- #

    def next_photo_index(self):
        if self.image_filenames:
            for filename in [f"class_{self.id}_1.jpg",
                             f"class_{self.id}_2.jpg",
                             f"class_{self.id}_3.jpg",
                             f"class_{self.id}_4.jpg",
                             f"class_{self.id}_5.jpg"]:
                if filename not in self.image_filenames:
                    return filename
            return None
        else:
            # Nothing yet, so
            return f"class_{self.id}_1.jpg"

    # ---------------------------------------------------------------------------------------------------------- #
    # Functions
    # ---------------------------------------------------------------------------------------------------------- #
    def all(self):
        with app.app_context():
            classifieds = db.session.query(Classified).order_by(Classified.id.desc()).all()
            return classifieds

    def all_by_email(self, email):
        with app.app_context():
            classifieds = db.session.query(Classified).filter_by(email=email).all()
            return classifieds

    def find_by_id(self, classified_id):
        with app.app_context():
            classified = db.session.query(Classified).filter_by(id=classified_id).first()
            return classified

    def number_photos(self, classified_id):
        with app.app_context():
            classified = db.session.query(Classified).filter_by(id=classified_id).first()
            if classified:
                filenames = classified.image_filenames.split(',')
                num_photos = 0
                for filename in filenames:
                    if filename != "":
                        num_photos += 1
                return num_photos
            else:
                app.logger.error(f"dB.number_photos(): Called with invalid classified_id = '{classified_id}'.")
                return None

    def add_classified(self, new_classified):
        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_classified)
                db.session.commit()
                # Return blog item
                return db.session.query(Classified).filter_by(id=new_classified.id).first()
            except Exception as e:
                app.logger.error(f"db.add_classified(): Failed with error code '{e.args}'.")
                return None

    def delete_classified(self, classified_id):
        with app.app_context():
            classified = db.session.query(Classified).filter_by(id=classified_id).first()
            if classified:
                try:
                    db.session.delete(classified)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_delete_classified: Failed to delete for classified_id = '{classified_id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    # Optional: this will allow each event object to be identified by its details when printed.
    def __repr__(self):
        return f'<Classified "{self.title}, by {self.email}">'


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

# This seems to be the only one which works?
with app.app_context():
    db.create_all()


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Forms
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def create_classified_form(num_photos: int):

    print(f"called with num_photos = '{num_photos}'")

    class Form(FlaskForm):

        # ----------------------------------------------------------- #
        # The form itself
        # ----------------------------------------------------------- #

        # Title
        title = StringField("What are you selling:",
                            validators=[InputRequired("Please enter a title.")])

        # Status
        status = SelectField("Status:", choices=STATUSES, validators=[])

        # Category
        category = SelectField("Category:", choices=CATEGORIES, validators=[])

        # Price
        price = StringField("What is the price eg '£20 ono':",
                            validators=[InputRequired("You must give a price.")])

        # Product details
        details = CKEditorField("Describe the item (the more detail the better):",
                                validators=[InputRequired("Please provide some details.")])

        if num_photos > 4:
            # Add image #1
            photo_filename_1 = FileField("1st image file:", validators=[])
        else:
            del_image_1 = SelectField(f"Delete 1st image of {MAX_NUM_PHOTOS - num_photos} already used:",
                                      choices=DEL_IMAGE, validators=[])

        if num_photos > 3:
            # Add image #2
            photo_filename_2 = FileField("2nd image file:", validators=[])
        else:
            del_image_2 = SelectField(f"Delete 2nd image of {MAX_NUM_PHOTOS - num_photos} already used:",
                                      choices=DEL_IMAGE, validators=[])

        if num_photos > 2:
            # Add image #3
            photo_filename_3 = FileField("3rd image file:", validators=[])
        else:
            del_image_3 = SelectField(f"Delete 3rd image of {MAX_NUM_PHOTOS - num_photos} already used:",
                                      choices=DEL_IMAGE, validators=[])

        if num_photos > 1:
            # Add image #4
            photo_filename_4 = FileField("4th image file:", validators=[])
        else:
            del_image_4 = SelectField(f"Delete 4th image of {MAX_NUM_PHOTOS - num_photos} already used:",
                                      choices=DEL_IMAGE, validators=[])

        if num_photos > 0:
            # Add image #5
            photo_filename_5 = FileField("5th image file:", validators=[])
        else:
            del_image_5 = SelectField(f"Delete 5th image of {MAX_NUM_PHOTOS - num_photos} already used:",
                                      choices=DEL_IMAGE, validators=[])

        # Buttons
        cancel = SubmitField("Maybe not")
        submit = SubmitField("Sell it all now!")

    return Form()


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    classifieds = db.session.query(Classified).all()
    print(f"Found {len(classifieds)} classifieds in the dB")
    app.logger.debug(f"Start of day: Found {len(classifieds)} classifieds in the dB")



