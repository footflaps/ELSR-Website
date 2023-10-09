from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired
import os
from datetime import datetime, timedelta
import time

# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db, GPX_UPLOAD_FOLDER_ABS

# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe
from core.dB_gpx import Gpx
from core.db_users import User

# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# These are our standard groups
TWR_CHOICE = "TWR"
GROUP_CHOICES = ["Decaff", "Espresso", "Doppio", "Mixed", TWR_CHOICE]

# Option for user defined choices
NEW_CAFE = "New cafe!"
UPLOAD_ROUTE = "Upload my own route!"

# Default option
DEFAULT_START = "8:00am from Bean Theory Cafe"


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Calendar Class
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

    # Added Unix date for sorting by ride date
    unix_date = db.Column(db.Integer)

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
            # We want them ordered by group so they are ordered on the webpage
            for group in GROUP_CHOICES:
                ride_set = db.session.query(Calendar).filter_by(date=ride_date).filter_by(group=group).all()
                for ride in ride_set:
                    rides.append(ride)
            return rides

    def all_calender_group_in_past(self, group: str):
        # Get current Unix Epoch time, plus a bit (6 hours)
        # This is because we add 2 hours to Unix Epoch timestamps to get round GMT/BST problem
        now = time.time() + 60 * 60 * 6
        with app.app_context():
            rides = db.session.query(Calendar).filter_by(group=group). \
                filter(Calendar.unix_date < now).order_by(Calendar.unix_date.desc()).all()
            return rides

    # Look up event by ID
    def one_ride_id(self, ride_id):
        with app.app_context():
            ride = db.session.query(Calendar).filter_by(id=ride_id).first()
            # Will return nothing if id is invalid
            return ride

    def all_rides_gpx_id(self, gpx_id):
        with app.app_context():
            rides = db.session.query(Calendar).filter_by(gpx_id=gpx_id).all()
            # Will return nothing if id is invalid
            return rides

    def add_ride(self, new_ride):
        # Add unix time
        date_obj = datetime(int(new_ride.date[4:8]), int(new_ride.date[2:4]), int(new_ride.date[0:2]), 0, 00)
        date_unix = datetime.timestamp(datetime.combine(date_obj, datetime.min.time()) + timedelta(hours=2))
        new_ride.unix_date = date_unix

        # Try and add to dB
        with app.app_context():
            try:
                db.session.add(new_ride)
                db.session.commit()
                # Have to re-acquire the message to return it (else we get Detached Instance Error)
                return db.session.query(Calendar).filter_by(id=new_ride.id).first()
            except Exception as e:
                app.logger.error(f"db_calendar: Failed to add ride '{new_ride}', "
                                 f"error code '{e.args}'.")
                return None

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


# # One off code to populate unix dates
# rides = Calendar().all_calendar()
# for ride in rides:
#     if not ride.unix_date:
#         date_obj = datetime(int(ride.date[4:8]), int(ride.date[2:4]), int(ride.date[0:2]), 0, 00)
#         date_unix = datetime.timestamp(datetime.combine(date_obj, datetime.min.time()) + timedelta(hours=2))
#         ride.unix_date = date_unix
#         Calendar().add_ride(ride)


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

# We create the form in a function as the form's select fields have to updated as we add users and rides etc,
# to databases. If we just create a class, then it runs once at start of day and never updates.

def create_ride_form(admin: bool, gpx_id=None):
    class Form(FlaskForm):

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
        gpx_choices = [UPLOAD_ROUTE]
        gpxes = Gpx().all_gpxes_sorted()
        for gpx in gpxes:
            filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
            # Route must be public and double check we have an actual GPX file on tap....
            if (gpx.public() and os.path.exists(filename)) \
                    or gpx.id == gpx_id:
                gpx_choices.append(gpx.combo_string())

        # ----------------------------------------------------------- #
        # Generate the list of users
        # ----------------------------------------------------------- #
        users = User().all_users_sorted()
        all_users = []
        for user in users:
            all_users.append(user.combo_str())

        # ----------------------------------------------------------- #
        # The form itself
        # ----------------------------------------------------------- #
        date = DateField("Which day is the ride for:", format='%Y-%m-%d', validators=[])

        # Admins have the ability to assign the ride to another user
        if admin:
            owner = SelectField("Owner (Admin only field):", choices=all_users, validators=[DataRequired()])

        leader = StringField("Ride Leader:", validators=[DataRequired()])
        start = StringField("Start time and location:", validators=[DataRequired()])
        destination = SelectField("Cafe:", choices=cafe_choices, validators=[DataRequired()])
        new_destination = StringField("If you're going to a new cafe, pray tell:", validators=[])
        group = SelectField("What pace is the ride:", choices=GROUP_CHOICES, validators=[DataRequired()])
        gpx_name = SelectField("Choose an existing route:", choices=gpx_choices, validators=[DataRequired()])
        gpx_file = FileField("or, upload your own GPX file:", validators=[])

        cancel = SubmitField('Cancel')
        submit = SubmitField("Add Ride")

    # Return the Class
    return Form()


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
    print(f"Found {len(rides)} calendar entries in the dB")
    app.logger.debug(f"Start of day: Found {len(rides)} calendar entries in the dB")
