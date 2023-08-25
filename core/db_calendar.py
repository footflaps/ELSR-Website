from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, SelectField, DateField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms.validators import DataRequired
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db, GPX_UPLOAD_FOLDER_ABS

from core.dB_cafes import Cafe
from core.dB_gpx import Gpx
from core.db_users import User


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# These are our standard groups
GROUP_CHOICES = ["Decaff", "Espresso", "Doppio", "Mixed"]

NEW_CAFE = "New cafe!"
UPLOAD_ROUTE = "Upload my own route!"
DEFAULT_START = "8:00am from Espresso Library, East Road"


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Event Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class Calendar(db.Model):
    # We're using multiple dBs with one instance of SQLAlchemy, so have to bind to the right one.
    __bind_key__ = 'calendar'

    id = db.Column(db.Integer, primary_key=True)

    # Who created the entry - will determine delete permissions
    email = db.Column(db.String(50))

    # Use string for date eg '13012023'
    date = db.Column(db.String(8))

    # Ride group eg 'Decaf', 'Doppio' etc
    group = db.Column(db.String(20))

    # Ride leader
    leader = db.Column(db.String(25))

    # Destination cafe eg 'Mill End Plants'
    destination = db.Column(db.String(50))

    # GPX ID, the route will exist in the gpx dB
    gpx_id = db.Column(db.Integer)

    # Cafe ID, the cafe might exist in the Cafe dB (could be a new cafe)
    cafe_id = db.Column(db.Integer)

    # Start time
    start_time = db.Column(db.String(250))

    # Return all events
    def all_calendar(self):
        with app.app_context():
            rides = db.session.query(Calendar).all()
            return rides

    # Return all events from a given user
    def all_calendar_email(self, email):
        with app.app_context():
            rides = db.session.query(Calendar).filter_by(email=email).all()
            # Will return nothing if email is invalid
            return rides

    # Return all events for a specific day
    def all_calendar_date(self, ride_date: str):
        with app.app_context():
            rides = []
            for group in GROUP_CHOICES:
                ride_set = db.session.query(Calendar).filter_by(date=ride_date).filter_by(group=group).all()
                for ride in ride_set:
                    rides.append(ride)
            return rides

    # Look up event by ID
    def one_ride_id(self, ride_id):
        with app.app_context():
            ride = db.session.query(Calendar).filter_by(id=ride_id).first()
            # Will return nothing if id is invalid
            return ride

    def add_ride(self, new_ride):

        # Try and add to dB
        with app.app_context():
            try:
                db.session.add(new_ride)
                db.session.commit()
                # Return new GPX id
                return True
            except Exception as e:
                app.logger.error(f"db_calendar: Failed to add ride '{new_ride}', "
                                 f"error code '{e.args}'.")
                return False

    # Delete a ride by id
    def delete_ride(self, ride_id):
        with app.app_context():
            ride = db.session.query(Calendar).filter_by(id=ride_id).first()
            if ride:
                # Delete the ride file
                try:
                    db.session.delete(ride)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_calendar: Failed to delete ride for ride_id = '{ride.id}', "
                                     f"error code '{e.args}'.")
        return False

    # Optional: this will allow each event object to be identified by its details when printed.
    def __repr__(self):
        return f'<Ride "{self.destination} , lead by {self.leader}">'


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

class CreateRideForm(FlaskForm):

    # ----------------------------------------------------------- #
    # Generate the list of cafes
    # ----------------------------------------------------------- #
    cafe_choices = []
    cafes = Cafe().all_cafes()
    for cafe in cafes:
        cafe_choices.append(cafe.combo_string())
    cafe_choices.append(NEW_CAFE)

    # ----------------------------------------------------------- #
    # Generate the list of routes
    # ----------------------------------------------------------- #
    gpx_choices = []
    gpxes = Gpx().all_gpxes_sorted()
    for gpx in gpxes:
        filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
        # Route must be public and double check we have an actual GPX file on tap....
        if gpx.public() \
                and os.path.exists(filename):
            gpx_choices.append(gpx.combo_string())
    gpx_choices.append(UPLOAD_ROUTE)

    # ----------------------------------------------------------- #
    # The form itself
    # ----------------------------------------------------------- #
    date = DateField("Which day is the ride for:", format='%Y-%m-%d', validators=[])
    leader = StringField("Ride Leader:", validators=[DataRequired()])
    destination = SelectField("Cafe:", choices=cafe_choices, validators=[DataRequired()])
    new_destination = StringField("If you're going to a new cafe, pray tell:", validators=[])
    group = SelectField("What pace is the ride:", choices=GROUP_CHOICES, validators=[DataRequired()])
    gpx_name = SelectField("Choose an existing route:", choices=gpx_choices, validators=[DataRequired()])
    gpx_file = FileField("or, upload your own GPX file:", validators=[])

    cancel = SubmitField('Cancel')
    submit = SubmitField("Add Ride")


class AdminCreateRideForm(FlaskForm):

    # ----------------------------------------------------------- #
    # Generate the list of cafes
    # ----------------------------------------------------------- #
    cafe_choices = []
    cafes = Cafe().all_cafes()
    for cafe in cafes:
        cafe_choices.append(cafe.combo_string())
    cafe_choices.append(NEW_CAFE)

    # ----------------------------------------------------------- #
    # Generate the list of routes
    # ----------------------------------------------------------- #
    gpx_choices = []
    gpxes = Gpx().all_gpxes_sorted()
    for gpx in gpxes:
        filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
        # Route must be public and double check we have an actual GPX file on tap....
        if gpx.public() \
                and os.path.exists(filename):
            gpx_choices.append(gpx.combo_string())
    gpx_choices.append(UPLOAD_ROUTE)

    # ----------------------------------------------------------- #
    # Generate the list of users
    # ----------------------------------------------------------- #

    users = User().all_users()
    all_users = []
    for user in users:
        all_users.append(f"{user.name} ({user.id})")

    # ----------------------------------------------------------- #
    # The form itself
    # ----------------------------------------------------------- #
    date = DateField("Which day is the ride for:", format='%Y-%m-%d', validators=[])
    owner = SelectField("Owner:", choices=all_users, validators=[DataRequired()])
    leader = StringField("Ride Leader:", validators=[DataRequired()])
    destination = SelectField("Cafe:", choices=cafe_choices, validators=[DataRequired()])
    new_destination = StringField("If you're going to a new cafe, pray tell:", validators=[])
    group = SelectField("What pace is the ride:", choices=GROUP_CHOICES, validators=[DataRequired()])
    gpx_name = SelectField("Choose an existing route:", choices=gpx_choices, validators=[DataRequired()])
    gpx_file = FileField("or, upload your own GPX file:", validators=[])

    cancel = SubmitField('Cancel')
    submit = SubmitField("Add Ride")


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    rides = db.session.query(Calendar).all()
    print(f"Found {len(rides)} events in the dB")