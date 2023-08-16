from flask_ckeditor import CKEditorField
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, SelectField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms.validators import DataRequired
from datetime import date
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db, app


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

ESPRESSO_LIBRARY_INDEX = 1
OPEN_CAFE_ICON = "https://maps.google.com/mapfiles/ms/icons/blue-dot.png"
CLOSED_CAFE_ICON = "https://maps.google.com/mapfiles/ms/icons/red-dot.png"

OPEN_CAFE_COLOUR = "#2196f3"
CLOSED_CAFE_COLOUR = "#922b21"



# -------------------------------------------------------------------------------------------------------------- #
# Define Cafe Class
# -------------------------------------------------------------------------------------------------------------- #

class Cafe(db.Model):
    # Don't need a bind key as this is the default database
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    # Allow cafes to be disabled (eg if they close) without removing from dB
    active = db.Column(db.Boolean, nullable=True)
    # Need lat and lon for map locations
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    # Optional website link and image url, which they can upload
    image_name = db.Column(db.String(250), nullable=True)
    website_url = db.Column(db.String(250), nullable=True)
    # Stick all the details in one text block
    details = db.Column(db.String(2000), nullable=True)
    summary = db.Column(db.String(100), nullable=True)
    rating = db.Column(db.String(100), nullable=True)
    # Who and when
    added_email = db.Column(db.String(250), nullable=False)
    added_date = db.Column(db.String(250), nullable=False)
    updated_date = db.Column(db.String(250), nullable=True)

    # Return a list of all cafes
    def all_cafes(self):
        with app.app_context():
            cafes = db.session.query(Cafe).order_by('name').all()
            return cafes

    # Return a single cafe
    def one_cafe(self, cafe_id):
        with app.app_context():
            cafe = db.session.query(Cafe).filter_by(id=cafe_id).first()
            # Will return nothing if id is invalid
            return cafe

    def find_by_name(self, name):
        with app.app_context():
            cafe = db.session.query(Cafe).filter_by(name=name).first()
            # Will return nothing if name is invalid
            return cafe

    # Add a new cafe to the dB
    def add_cafe(self, new_cafe):

        # Update some details
        new_cafe.added_date = date.today().strftime("%B %d, %Y")
        new_cafe.active = True

        # Try and add to dB
        with app.app_context():
            try:
                db.session.add(new_cafe)
                db.session.commit()
                # Return success
                return True
            except Exception as e:
                app.logger.error(f"dB.add_cafe(): Failed to add cafe '{new_cafe.name}', error code was '{e.args}'.")
                return False

    # Update an existing cafe
    def update_cafe(self, cafe_id, updated_cafe):
        with app.app_context():
            cafe = db.session.query(Cafe).filter_by(id=cafe_id).first()
            if cafe:
                cafe.name = updated_cafe.name
                cafe.lat = updated_cafe.lat
                cafe.lon = updated_cafe.lon
                cafe.website_url= updated_cafe.website_url
                cafe.details = updated_cafe.details
                cafe.summary = updated_cafe.summary
                cafe.rating = updated_cafe.rating
                try:
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.update_cafe(): Failed with cafe '{cafe.name}', error code was '{e.args}'.")
                    return False
        app.logger.error(f"dB.update_cafe(): Failed to with cafe '{cafe.name}', invalid cafe_id='{cafe_id}'.")
        return False

    def update_photo(self, cafe_id, filename):
        with app.app_context():
            cafe = db.session.query(Cafe).filter_by(id=cafe_id).first()
            if cafe:
                try:
                    cafe.image_name = filename
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.update_photo(): Failed with cafe '{cafe.name}', error code was '{e.args}'.")
                    return False
        return False

    # Mark a cafe as being closed or closing
    def close_cafe(self, cafe_id, details):
        with app.app_context():
            cafe = db.session.query(Cafe).get(cafe_id)
            # Found one?
            if cafe:
                try:
                    # Delete the cafe
                    cafe.active = None
                    cafe.details = f"<b style='color:red'>{date.today().strftime('%B %d, %Y')} " \
                                   f"This cafe has been marked as closed or closing: {details}</b><br>{cafe.details}"
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.close_cafe(): Failed with cafe '{cafe.name}', error code was '{e.args}'.")
                    return False
        return False

    # Mark a cafe as no longer being closed
    def unclose_cafe(self, cafe_id):
        with app.app_context():
            cafe = db.session.query(Cafe).get(cafe_id)
            # Found one?
            if cafe:
                try:
                    # Delete the cafe
                    cafe.active = True
                    cafe.details = f"<b style='color:red'>{date.today().strftime('%B %d, %Y')} " \
                                   f"Rejoice! This is no longer closing!</b><br>{cafe.details}"
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.unclose_cafe(): Failed with cafe '{cafe.name}', error code was '{e.args}'.")
                    return False
        return False

    def find_all_cafes_by_email(self, email):
        with app.app_context():
            cafes = db.session.query(Cafe).filter_by(added_email=email).all()
            return cafes

    def cafe_list(self, cafes_passed):
        # Take the cafe_passed JSON string from the GPX data base and from it, returns the details of the
        # Cafes which were referenced in the string (referenced by id).

        cafes_json = json.loads(cafes_passed)

        # We will return this
        cafe_list = []

        for cafe_json in cafes_json:
            cafe_id = cafe_json['cafe_id']
            cafe = self.one_cafe(cafe_id)
            if cafe:
                cafe_summary = {
                    'id': cafe_id,
                    'name': cafe.name,
                    'lat': cafe.lat,
                    'lon': cafe.lon,
                    'dist_km': cafe_json['dist_km'],
                    'range_km': cafe_json['range_km'],
                    'status': cafe.active,
                }
                cafe_list.append(cafe_summary)

        return sorted(cafe_list, key=lambda x: x['range_km'])

    # Optional: this will allow each blog object to be identified by its name when printed.
    def __repr__(self):
        return f'<Blog {self.title}>'


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

# This seems to be the only one which works?
with app.app_context():
    db.create_all()


# -------------------------------------------------------------------------------------------------------------- #
# Create our upload forms
# -------------------------------------------------------------------------------------------------------------- #

class CreateCafeForm(FlaskForm):
    name = StringField("Cafe name", validators=[DataRequired()])
    lat = FloatField("Latitude", validators=[DataRequired()])
    lon = FloatField("Longitude", validators=[DataRequired()])
    website_url = StringField("Website URL", validators=[])
    summary = StringField("Five word summary", validators=[DataRequired()])
    rating = SelectField("Overall rating for a cycling cafe ride",
                         choices=["☕️", "☕☕", "☕☕☕", "☕☕☕☕", "☕☕☕☕☕"],
                         validators=[DataRequired()])
    cafe_photo = FileField("Image file for the cafe.", validators=[])

    # Use the full feature editor for the details section
    detail = CKEditorField("Details", validators=[DataRequired()])

    submit = SubmitField("Submit")


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    cafes = db.session.query(Cafe).all()
    print(f"Found {len(cafes)} cafes in the dB")


# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #

# Jinja needs to be able to look up the cafe name from it's id when resolving comments on the user's page


def get_cafe_name_from_id(cafe_id):
    return Cafe().one_cafe(cafe_id).name


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(get_cafe_name_from_id=get_cafe_name_from_id)