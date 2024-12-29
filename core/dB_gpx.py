from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField
from flask_ckeditor import CKEditorField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired, Length, InputRequired
from datetime import date, datetime
import json
from sqlalchemy import func


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db, GRAVEL_CHOICE
from core.db_users import User
from core.subs_gpx_direction import gpx_direction
from core.database.models.gpx_model import GpxModel


# -------------------------------------------------------------------------------------------------------------- #
# Constants used for uploading routes
# -------------------------------------------------------------------------------------------------------------- #

GPX_ALLOWED_EXTENSIONS = {'gpx'}
TYPE_GRAVEL = GRAVEL_CHOICE
TYPE_ROAD = "Road"
TYPES = [TYPE_ROAD,
         TYPE_GRAVEL,
         "MTB"]


# -------------------------------------------------------------------------------------------------------------- #
# Define GPX Class
# -------------------------------------------------------------------------------------------------------------- #

class Gpx(GpxModel):

    # -------------------------------------------------------------------------------------------------------------- #
    # Properties
    # -------------------------------------------------------------------------------------------------------------- #

    def public(self):
        return self.valid == 1

    # -------------------------------------------------------------------------------------------------------------- #
    # Functions
    # -------------------------------------------------------------------------------------------------------------- #

    def all_gpxes(self):
        with app.app_context():
            gpxes = db.session.query(Gpx).all()
            return gpxes

    def all_gpxes_sorted_downloads(self):
        with app.app_context():
            gpxes = db.session.query(Gpx).filter_by(valid=1).order_by(func.json_array_length(Gpx.downloads).desc()).\
                    limit(10).all()
            return gpxes

    # Alphabetical list for combobox selection
    def all_gpxes_sorted(self):
        with app.app_context():
            gpxes = db.session.query(Gpx).order_by('name').all()
            return gpxes

    def all_gravel(self):
        with app.app_context():
            gpxes = db.session.query(Gpx).filter_by(type=TYPE_GRAVEL).all()
            return gpxes

    def all_gpxes_by_email(self, email):
        with app.app_context():
            gpxes = db.session.query(Gpx).filter_by(email=email).all()
            return gpxes

    def one_gpx(self, gpx_id):
        with app.app_context():
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()
            return gpx

    # Add a new gpx file to the dB
    def add_gpx(self, new_gpx):

        # Update some details
        new_gpx.date = date.today().strftime("%d%m%Y")

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
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()
            if gpx:
                try:
                    # Update filename
                    gpx.filename = filename
                    gpx.direction = gpx_direction(filename, gpx_id)
                    # Write to dB
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_gpx: Failed to update filename for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    def update_downloads(self, gpx_id, email):
        with app.app_context():
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()
            if gpx:
                try:
                    # Update filename
                    if gpx.downloads:
                        emails = json.loads(gpx.downloads)
                        if not email in emails:
                            emails.append(email)
                    else:
                        # Start new set
                        emails = [email]
                    # Write to dB
                    gpx.downloads = json.dumps(emails)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_gpx: Failed to update downloads for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    def clear_cafe_list(self, gpx_id):
        with app.app_context():
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()
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
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()
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
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()
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
            gpx = db.session.query(Gpx).filter_by(id=gpx_id).first()
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

    def combo_string(self):
        return f"{self.name}, {self.length_km}km / {self.ascent_m}m ({self.id})"

    def gpx_id_from_combo_string(self, combo_string):
        # Extract id from number in last set of brackets
        gpx_id = combo_string.split('(')[-1].split(')')[0]
        return gpx_id


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
    type = SelectField("Type of route:", choices=TYPES,
                       validators=[InputRequired("Please enter a type.")])
    details = CKEditorField("If gravel, add any useful details:", validators=[])
    filename = FileField("", validators=[DataRequired()])

    submit = SubmitField("Upload GPX")


# -------------------------------------------------------------------------------------------------------------- #
# Edit route name form
# -------------------------------------------------------------------------------------------------------------- #

def create_rename_gpx_form(admin: bool):

    # ----------------------------------------------------------- #
    # Generate the list of users
    # ----------------------------------------------------------- #
    users = User().all_users_sorted()
    all_users = []
    for user in users:
        all_users.append(f"{user.name} ({user.id})")

    class Form(FlaskForm):
        name = StringField("Route name eg 'Hilly route to Mill End Plants'", validators=[Length(min=6, max=50)])

        type = SelectField("Type of route:", choices=TYPES,
                           validators=[InputRequired("Please enter a type.")])

        details = CKEditorField("If gravel, add any useful details:", validators=[])

        # Admin can assign ownership
        if admin:
            owner = SelectField("Owner (Admin only field):", choices=all_users, validators=[DataRequired()])

        submit = SubmitField("Update")

    return Form()


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
    app.logger.debug(f"Start of day: Found {len(gpxes)} GPXes in the dB")


# -------------------------------------------------------------------------------------------------------------- #
# One off hack to set direction
# -------------------------------------------------------------------------------------------------------------- #
# with app.app_context():
#     gpxes = Gpx().all_gpxes()
#     for gpx in gpxes:
#         direction = gpx_direction(gpx)
#         print(f"ID = '{gpx.id}', Direction = '{direction}'")
#         app.logger.debug(f"ID = '{gpx.id}', Direction = '{direction}'")
#         gpx.direction = direction
#         db.session.add(gpx)
#         db.session.commit()

# # Test GPX Direction
# gpxes = Gpx().all_gpxes()
# for gpx in gpxes:
#         direction = gpx_direction(gpx.filename, gpx.id)
#         print(f"ID = '{gpx.id}', Direction = '{direction}'")


# -------------------------------------------------------------------------------------------------------------- #
# Hack to change date
# -------------------------------------------------------------------------------------------------------------- #

# with app.app_context():
#     gpxes = Gpx().all_gpxes()
#     for gpx in gpxes:
#         if len(gpx.date) != 8:
#             date_obj = datetime.strptime(gpx.date, "%B %d, %Y")
#             new_date = date_obj.strftime("%d%m%Y")
#             print(f"ID = {gpx.id}, Name = '{gpx.name}', Date = '{gpx.date}' or '{new_date}'")
#             gpx.date = new_date
#             db.session.add(gpx)
#             db.session.commit()
