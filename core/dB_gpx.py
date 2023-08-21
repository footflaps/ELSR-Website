from flask_ckeditor import CKEditorField
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, SelectField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms.validators import DataRequired, Length
from datetime import date
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db, GPX_UPLOAD_FOLDER_ABS


# -------------------------------------------------------------------------------------------------------------- #
# Constants used for uploading routes
# -------------------------------------------------------------------------------------------------------------- #

GPX_ALLOWED_EXTENSIONS = {'gpx'}


# -------------------------------------------------------------------------------------------------------------- #
# Define GPX Class
# -------------------------------------------------------------------------------------------------------------- #

class Gpx(db.Model):

    # We're using multiple dBs with one instance of SQLAlchemy, so have to bind to the right one.
    __bind_key__ = 'gpx'

    # Primary reference
    id = db.Column(db.Integer, primary_key=True)

    # Filename
    filename = db.Column(db.String(250), unique=True, nullable=False)

    # Original target cafe (this will be a string)
    name = db.Column(db.String(250), nullable=False)

    # Derive stats for the file
    length_km = db.Column(db.Float, nullable=False)
    ascent_m = db.Column(db.Float, nullable=False)

    # This will be a JSON of cafe details for cafes passed
    # eg [
    #      {"cafe_id": 1, "dist_km": 0.1, "range_km": 70},
    #      {"cafe_id": 2, "dist_km": 0.2, "range_km": 30}
    #    ]
    cafes_passed = db.Column(db.String(3000), nullable=False)

    # Who and when uploaded it
    email = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)

    # Is the GPX valid
    valid = db.Column(db.Integer, nullable=True)


    def public(self):
        return self.valid == 1

    def all_gpxes(self):
        with app.app_context():
            gpxes = db.session.query(Gpx).all()
            return gpxes

    def all_gpxes_by_email(self, email):
        with app.app_context():
            gpxes = db.session.query(Gpx).filter_by(email=email).all()
            return gpxes

    def one_gpx(self, gpx_id):
        with app.app_context():
            gpx = db.get_or_404(Gpx, gpx_id)
            return gpx

    # Add a new gpx file to the dB
    def add_gpx(self, new_gpx):

        # Update some details
        new_gpx.date = date.today().strftime("%B %d, %Y")

        # Try and add to dB
        with app.app_context():
            try:
                db.session.add(new_gpx)
                db.session.commit()
                # Return new GPX id
                return new_gpx.id
            except Exception as e:
                app.logger.error(f"db_gpx: Failed to add GPX '{new_gpx.name}', "
                                 f"error code '{e.args}'.")
                return False

    def delete_gpx(self, gpx_id):
        with app.app_context():

            # Locate the GPX file
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()

            if gpx:
                # Delete the GPX file
                try:
                    db.session.delete(gpx)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_gpx: Failed to delete GPX for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    def update_filename(self, gpx_id, filename):
        with app.app_context():

            # Locate the GPX file
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()

            if gpx:
                try:
                    # Update filename
                    gpx.filename = filename
                    # Write to dB
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_gpx: Failed to update filename for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    def clear_cafe_list(self, gpx_id):
        with app.app_context():

            # Locate the GPX file
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()

            # Did we get something?
            if gpx:
                try:
                    # Note, the cafes_passed is a JSON string, not a list!
                    gpx.cafes_passed = "[]"
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_gpx: Failed to clear cafe list for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    def update_cafe_list(self, gpx_id, cafe_id, dist_km, range_km):
        with app.app_context():

            # Locate the GPX file
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()

            # Did we get something?
            if gpx:
                try:
                    # Get the list of cafes passed
                    # eg [  {"cafe_id": 1, "dist_km": 0.1, "range_km": 70},
                    #       {"cafe_id": 2, "dist_km": 0.2, "range_km":30}
                    #    ]
                    cafes_json = json.loads(gpx.cafes_passed)
                    updated = False

                    for cafe in cafes_json:
                        if cafe['cafe_id'] == cafe_id:
                            cafe['dist_km'] = round(dist_km,1)
                            cafe['range_km'] = round(range_km,1)
                            updated = True

                    if not updated:
                        # Tag on the end
                        cafes_json.append({
                            "cafe_id": cafe_id,
                            "dist_km": round(dist_km,1),
                            "range_km": round(range_km,1)
                        })

                    # Push back to gpx
                    gpx.cafes_passed = json.dumps(cafes_json)

                    # Update dB
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_gpx: Failed to update cafe list for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    def remove_cafe_list(self, gpx_id, cafe_id):
        with app.app_context():

            # Locate the GPX file
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()

            # Did we get something?
            if gpx:
                try:
                    # Get the list of cafes passed
                    # eg [  {"cafe_id": 1, "dist_km": 0.1, "range_km": 70},
                    #       {"cafe_id": 2, "dist_km": 0.2, "range_km":30}
                    #    ]
                    cafes_json = json.loads(gpx.cafes_passed)

                    for cafe in cafes_json:
                        if cafe['cafe_id'] == cafe_id:
                            # Need to remove this entry
                            cafes_json.remove(cafe)

                    # Push back to gpx
                    gpx.cafes_passed = json.dumps(cafes_json)

                    # Update dB
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_gpx: Failed to update cafe list for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    # Add length and ascent to the database
    def update_stats(self, gpx_id, length_km, ascent_m):
        with app.app_context():
            # Locate the GPX file
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()
            # Did we get something?
            if gpx:
                try:
                    # Update route stats
                    gpx.length_km = round(length_km,1)
                    gpx.ascent_m = round(ascent_m,1)
                    # Update dB
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_gpx: Failed to update stats for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False
            return False

    def find_all_gpx_for_cafe(self, cafe_id, user):
        # We return a list of GPXes which pass this cafe
        passing_gpx = []
        for gpx in self.all_gpxes():

            # Tortuous logic as current_user won't have '.email' until authenticated....
            if gpx.public():
                can_see = True
            elif not user.is_authenticated:
                can_see = False
            elif user.email == gpx.email:
                can_see = True
            else:
                can_see = False

            if can_see:
                cafes_json = json.loads(gpx.cafes_passed)
                for cafe in cafes_json:
                    if cafe['cafe_id'] == cafe_id:
                        # Alter the GPX object to just have one cafe passed as this is all the
                        # requesting webpage needs to know (it only cares about one cafe)
                        gpx.cafes_passed = cafe
                        passing_gpx.append(gpx)
        return passing_gpx

    def publish(self, gpx_id):
        with app.app_context():
            # Locate the GPX file
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()
            if gpx:
                try:
                    gpx.valid = 1
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_gpx: Failed to publish gpx for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    def hide(self, gpx_id):
        with app.app_context():
            # Locate the GPX file
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()
            if gpx:
                try:
                    gpx.valid = None
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_gpx: Failed to hide gpx for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    db.create_all()


# -------------------------------------------------------------------------------------------------------------- #
# Create our upload forms
# -------------------------------------------------------------------------------------------------------------- #

class UploadGPXForm(FlaskForm):
    name = StringField("Route name eg 'Hilly route to Mill End Plants'", validators=[Length(min=6, max=50)])
    filename = FileField("", validators=[DataRequired()])

    submit = SubmitField("Upload GPX")


# -------------------------------------------------------------------------------------------------------------- #
# Jinja needs to know how many routes pass a cafe for the cafe page
# -------------------------------------------------------------------------------------------------------------- #

def number_routes_passing_by(cafe_id, user):
    routes = Gpx().find_all_gpx_for_cafe(cafe_id, user)
    return len(routes)

app.jinja_env.globals.update(number_routes_passing_by=number_routes_passing_by)


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    gpxes = db.session.query(Gpx).all()
    print(f"Found {len(gpxes)} GPXes in the dB")