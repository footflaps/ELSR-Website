from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField, validators, TimeField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired
import os
from datetime import datetime, timedelta
import time

# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db, GPX_UPLOAD_FOLDER_ABS, GROUP_CHOICES

# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe
from core.dB_gpx import Gpx
from core.db_users import User

# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Option for user defined choices
NEW_CAFE = "New cafe!"
UPLOAD_ROUTE = "Upload my own route!"

# Options for where the rides start
MEETING_OTHER = "Other..."
MEETING_BEAN = "Bean Theory Cafe"
MEETING_COFFEE_VANS = "Coffee Vans by the Station"
MEETING_TWR = "The Bench, Newnham Corner"
MEETING_CHOICES = [MEETING_BEAN,
                   MEETING_COFFEE_VANS,
                   MEETING_OTHER]

# Used by JS on the create ride page to auto fill in the start details based on the day of week
DEFAULT_START_TIMES = {"Monday": {'time': '08:00', 'location': MEETING_BEAN, 'new': ''},
                       "Tuesday": {'time': '08:00', 'location': MEETING_BEAN, 'new': ''},
                       "Wednesday": {'time': '08:00', 'location': MEETING_OTHER, 'new': MEETING_TWR},
                       "Thursday": {'time': '08:00', 'location': MEETING_BEAN, 'new': ''},
                       "Friday": {'time': '08:00', 'location': MEETING_BEAN, 'new': ''},
                       "Saturday": {'time': '08:00', 'location': MEETING_BEAN, 'new': ''},
                       "Sunday": {'time': '09:00', 'location': MEETING_BEAN, 'new': ''},
                       }


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Calendar Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class Calendar(db.Model):
    __tablename__ = 'calendar'
    __table_args__ = {'schema': 'elsr'}

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
    destination = db.Column(db.String(200))

    # GPX ID, the route will exist in the gpx dB
    gpx_id = db.Column(db.Integer)

    # Cafe ID, the cafe might exist in the Cafe dB (could be a new cafe)
    cafe_id = db.Column(db.Integer)

    # Start time
    start_time = db.Column(db.String(250))

    # Added Unix date for sorting by ride date
    unix_date = db.Column(db.Integer)

    # Column to denote whether we sent an email or not
    sent_email = db.Column(db.String(20))

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

    def mark_email_sent(self, ride_id):
        with app.app_context():
            ride = db.session.query(Calendar).filter_by(id=ride_id).first()
            if ride:
                # Modify
                try:
                    ride.sent_email = "True"
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_calendar: Failed to set email sent for ride_id = '{ride.id}', "
                                     f"error code '{e.args}'.")
        return False

    # Optional: this will allow each event object to be identified by its details when printed.
    def __repr__(self):
        return f'<Ride "{self.destination} , lead by {self.leader}">'


# One off code to set sent_email
# with app.app_context():
#     rides = Calendar().all_calendar()
#     for ride in rides:
#         if ride.sent_email != "True":
#             ride.sent_email = "True"
#             db.session.add(ride)
#             db.session.commit()


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

# -------------------------------------------------------------------------------------------------------------- #
# Custom validator for termination date (must be in the future)
# -------------------------------------------------------------------------------------------------------------- #
def date_validation(form, field):
    # This will be '<class 'datetime.date'>'
    today_date = datetime.today().date()
    # This can be either  '<class 'datetime.date'>' or '<class 'datetime.datetime'>'
    ride_date = field.data
    # Convert to date object as we can't compare date vs datetime
    if type(ride_date) == datetime:
        ride_date = ride_date.date()
    # Might not be set...
    if ride_date:
        if ride_date < today_date:
            raise validators.ValidationError('That date is in the past!')


# -------------------------------------------------------------------------------------------------------------- #
# Custom validator for filling in New Start location (if they select Other, they must fill in the location)
# -------------------------------------------------------------------------------------------------------------- #
def start_validation(form, field):
    start_option = form.start_location.data
    if start_option == MEETING_OTHER:
        if field.data.strip() == "":
            raise validators.ValidationError(f"You must enter an alternate meeting point "
                                             f"if you select '{MEETING_OTHER}'")
    elif field.data.strip() != "":
        raise validators.ValidationError(f"You must leave this blank unless you have selected '{MEETING_OTHER}'")


# -------------------------------------------------------------------------------------------------------------- #
# Custom validator for filling in Destination (if they select New Cafe, they must fill in the location)
# -------------------------------------------------------------------------------------------------------------- #
def destination_validation(form, field):
    cafe_option = form.destination.data
    if cafe_option == NEW_CAFE:
        if field.data.strip() == "":
            raise validators.ValidationError(f"You must enter the name of the new cafe if you select '{NEW_CAFE}'")
    elif field.data.strip() != "":
        raise validators.ValidationError(f"You must leave this blank unless you have selected '{NEW_CAFE}'")


# -------------------------------------------------------------------------------------------------------------- #
# The form itself
# -------------------------------------------------------------------------------------------------------------- #
# We create the form in a function as the form's select fields have to updated as we add users and rides etc,
# to databases. If we just create a class, then it runs once at start of day and never updates.

def create_ride_form(admin: bool, gpx_id=None):
    class Form(FlaskForm):

        # ----------------------------------------------------------- #
        # Generate the list of cafes
        # ----------------------------------------------------------- #
        cafe_choices = []
        cafes = Cafe().all_cafes_sorted()
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
        # Admins can create events in the past, users can't
        # Mainly to allow me to backfill ride history
        if admin:
            date = DateField("Which day is the ride for:", format='%Y-%m-%d', validators=[])
        else:
            date = DateField("Which day is the ride for:", format='%Y-%m-%d', validators=[date_validation])

        # Admins have the ability to assign the ride to another user
        if admin:
            owner = SelectField("Owner (Admin only field):", choices=all_users, validators=[DataRequired()])

        # Leader and group
        leader = StringField("Ride Leader:", validators=[DataRequired()])
        group = SelectField("What pace is the ride:", choices=GROUP_CHOICES, validators=[DataRequired()])

        # Split start into three parts
        start_time = TimeField("Meeting time:", format="%H:%M")
        start_location = SelectField("Meeting point:", choices=MEETING_CHOICES)
        other_location = StringField(f"New start location (use with '{MEETING_OTHER}'):", validators=[start_validation])

        # Destination
        destination = SelectField("Cafe:", choices=cafe_choices, validators=[DataRequired()])
        new_destination = StringField("If you're going to a new cafe, pray tell:", validators=[destination_validation])

        # Route details
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
# Convert the dictionary entry into a single string
# -------------------------------------------------------------------------------------------------------------- #
def start_time_string(start_time_dict):
    if start_time_dict['location'] != MEETING_OTHER:
        return f"{start_time_dict['time']} from {start_time_dict['location']}"
    else:
        return f"{start_time_dict['time']} from {start_time_dict['new']}"


# -------------------------------------------------------------------------------------------------------------- #
# Return the default start time for a given day as html
# -------------------------------------------------------------------------------------------------------------- #
def default_start_time_html(day):
    # Look up what we would normally expect for day 'day'
    default_time = DEFAULT_START_TIMES[day]['time']
    if DEFAULT_START_TIMES[day]['location'] != MEETING_OTHER:
        default_location = DEFAULT_START_TIMES[day]['location']
    else:
        default_location = DEFAULT_START_TIMES[day]['new']

    return f"<strong>{default_time}</strong> from <strong>{default_location}</strong>"


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(default_start_time_html=default_start_time_html)


# -------------------------------------------------------------------------------------------------------------- #
# Return a custom start time as an html string
# -------------------------------------------------------------------------------------------------------------- #

def custom_start_time_html(day, start_time_str):
    # Look up what we would normally expect for day 'day'
    default_time = DEFAULT_START_TIMES[day]['time']
    if DEFAULT_START_TIMES[day]['location'] != MEETING_OTHER:
        default_location = DEFAULT_START_TIMES[day]['location']
    else:
        default_location = DEFAULT_START_TIMES[day]['new']

    # Now parse actual string
    # We expect the form "Doppio", "Danish Camp", "08:00 from Bean Theory Cafe" etc
    # Split "08:00" from "from Bean Theory Cafe"
    time = start_time_str.split(' ')[0]
    location = " ".join(start_time_str.split(' ')[2:])

    # Build our html string
    if default_time == time:
        html = f"<strong>{time}</strong>"
    else:
        html = f"<strong style='color: red'>{time}</strong>"

    if default_location == location:
        html += f" from <strong>{location}</strong>"
    else:
        html += f" from <strong style='color:red'>{location}</strong>"

    return html


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(custom_start_time_html=custom_start_time_html)


# -------------------------------------------------------------------------------------------------------------- #
# Convert date from '11112023' to '11/11/2023' as more user friendly
# -------------------------------------------------------------------------------------------------------------- #

def beautify_date(date: str):
    # Check we have been passed a string in the right format
    if len(date) != 8:
        # Just pass it back to be displayed as is
        return date
    return f"{date[0:2]}/{date[2:4]}/{date[4:9]}"


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(beautify_date=beautify_date)


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    rides = db.session.query(Calendar).all()
    print(f"Found {len(rides)} calendar entries in the dB")
    app.logger.debug(f"Start of day: Found {len(rides)} calendar entries in the dB")
