from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField
from flask_ckeditor import CKEditorField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired, Length, InputRequired
from datetime import date
import json
from sqlalchemy import func
import math
import numpy
import os
import gpxpy
import gpxpy.gpx
import mpu


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db, GRAVEL_CHOICE, GPX_UPLOAD_FOLDER_ABS
from core.db_users import User
from core.dB_events import Event


# -------------------------------------------------------------------------------------------------------------- #
# Constants used for uploading routes
# -------------------------------------------------------------------------------------------------------------- #

GPX_ALLOWED_EXTENSIONS = {'gpx'}
TYPE_GRAVEL = GRAVEL_CHOICE
TYPE_ROAD = "Road"
TYPES = [TYPE_ROAD,
         TYPE_GRAVEL,
         "MTB"]

# Maximum distance we allow between start and finish to consider route circular
MAX_CIRCULAR_DELTA_KM = 10.0


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

    # Type (road / offroad)
    type = db.Column(db.String(20))

    # Details (really just for offroad routes)
    details = db.Column(db.Text)

    # Number times downloaded
    downloads = db.Column(db.Text)

    # Clockwise, Anticlockwise or N/A
    direction = db.Column(db.Text)

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
                    gpx.direction = gpx_direction(gpx)
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

    # Optional: this will allow each event object to be identified by its details when printed.
    def __repr__(self):
        return f'<GPX "{self.name}">'


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
# Work out if a route is Clockwise or anti-Clockwise
# -------------------------------------------------------------------------------------------------------------- #
def gpx_direction(gpx: Gpx()):
    # Make sure gpx_id is valid
    if not gpx:
        app.logger.debug(f"gpx_direction(): Called with invalid Gpx.")
        Event().log_event("gpx_direction Fail", f"Called with invalid Gpx.")
        return "Error"

    # ----------------------------------------------------------- #
    # Check we have an actual file
    # ----------------------------------------------------------- #

    # Use absolute path for filename
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

    # Check GPX file actually exists
    if not os.path.exists(filename):
        app.logger.debug(f"gpx_direction(): Failed to locate file: gpx_id = '{gpx.id}'.")
        Event().log_event("gpx_direction Fail", f"Failed to locate file: gpx_id = '{gpx.id}'.")
        return "Missing File"

    # ----------------------------------------------------------- #
    # Work out the direction the route goes in
    # ----------------------------------------------------------- #

    # Open and parse the file
    with open(filename, 'r') as file_ref:

        gpx_file = gpxpy.parse(file_ref)

        for track in gpx_file.tracks:
            for segment in track.segments:

                # We'll need these
                start_lat = segment.points[0].latitude
                start_lon = segment.points[0].longitude
                app.logger.debug(f"start_lat = '{start_lat}', start_lon = '{start_lon}'")

                num_points = len(segment.points)

                # Outward point is 25% along the path
                out_lat = segment.points[math.floor(num_points*0.25)].latitude
                out_lon = segment.points[math.floor(num_points*0.25)].longitude
                app.logger.debug(f"out_lat = '{out_lat}', out_lon = '{out_lon}'")

                # Return point is 75% along the path
                ret_lat = segment.points[math.floor(num_points * 0.75)].latitude
                ret_lon = segment.points[math.floor(num_points * 0.75)].longitude
                app.logger.debug(f"ret_lat = '{ret_lat}', ret_lon = '{ret_lon}'")

                # Last point
                last_lat = segment.points[-1].latitude
                last_lon = segment.points[-1].longitude
                app.logger.debug(f"last_lat = '{last_lat}', last_lon = '{last_lon}'")

    # ----------------------------------------------------------- #
    # Derive angle of two vectors
    # ----------------------------------------------------------- #
    return cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, last_lat, last_lon, False)


def cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, last_lat, last_lon, debug):
    # ----------------------------------------------------------- #
    # Check for circular route
    # ----------------------------------------------------------- #
    dist_km = mpu.haversine_distance((last_lat, last_lon), (start_lat, start_lon))
    if dist_km > MAX_CIRCULAR_DELTA_KM:
        # Not circular, so can't derive CW / ACW
        return "Not Circular"

    # ----------------------------------------------------------- #
    # Derive angle of two vectors
    # ----------------------------------------------------------- #
    outward_angle_deg = numpy.arctan2(out_lat - start_lat, out_lon - start_lon) / math.pi * 180
    return_angle_deg = numpy.arctan2(ret_lat - start_lat, ret_lon - start_lon) / math.pi * 180

    if debug:
        print(f"outward_angle_deg = '{round( outward_angle_deg, 3)}', return_angle_deg = '{round(return_angle_deg, 3)}'")

    # ----------------------------------------------------------- #
    # We have to cope with two exceptions, the vectors spanning 180/-180
    # ----------------------------------------------------------- #
    if outward_angle_deg > 90 and \
            return_angle_deg < -90:
        return_angle_deg += 360

    if return_angle_deg > 90 and \
            outward_angle_deg < -90:
        outward_angle_deg += 360

    # ----------------------------------------------------------- #
    # Make them both +ve
    # ----------------------------------------------------------- #
    if outward_angle_deg > return_angle_deg:
        return "CW"
    else:
        return "CCW"


def test_cw_ccw():
    start_lon = 52.2
    start_lat = 0.11
    range_deg = 0.2

    # 0 deg = due North, 90 deg = due East
    for deg in range(-90, 391, 10):
        out_deg = deg
        ret_deg = deg - 20

        out_lat = start_lat + math.sin(out_deg/180 * math.pi) * range_deg
        out_lon = start_lon + math.cos(out_deg/180 * math.pi) * range_deg
        ret_lat = start_lat + math.sin(ret_deg / 180 * math.pi) * range_deg
        ret_lon = start_lon + math.cos(ret_deg / 180 * math.pi) * range_deg

        if cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, False) == "CW":
            pass
        else:
            print("CW FAIL")
            print(f"deg = '{deg}'")
            print(f"out_deg = '{out_deg}': out_lon = '{round(out_lon, 3)}', out_lat = '{round(out_lat, 3)}'")
            print(f"ret_deg = '{ret_deg}': ret_lon = '{round(ret_lon, 3)}',ret_lat = '{round(ret_lat, 3)}'")
            cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, True)

    for deg in range(-90, 391, 10):
        out_deg = deg
        ret_deg = deg + 20

        out_lat = start_lat + math.sin(out_deg / 180 * math.pi) * range_deg
        out_lon = start_lon + math.cos(out_deg / 180 * math.pi) * range_deg
        ret_lat = start_lat + math.sin(ret_deg / 180 * math.pi) * range_deg
        ret_lon = start_lon + math.cos(ret_deg / 180 * math.pi) * range_deg

        if cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, False) == "CCW":
            pass
        else:
            print("CCW FAIL")
            print(f"deg = '{deg}'")
            print(f"out_deg = '{out_deg}': out_lon = '{round(out_lon, 3)}', out_lat = '{round(out_lat, 3)}'")
            print(f"ret_deg = '{ret_deg}': ret_lon = '{round(ret_lon, 3)}',ret_lat = '{round(ret_lat, 3)}'")
            cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, True)

# test_cw_ccw()


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
