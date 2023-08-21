from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, SelectField, DateField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms.validators import DataRequired


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db

from core.dB_cafes import Cafe
from core.dB_gpx import Gpx


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# These are our standard groups
GROUP_CHOICES = ["Decaff", "Espresso", "Doppio", "Mixed"]


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

    # Return all events
    def all_calendar(self):
        with app.app_context():
            rides = db.session.query(Calendar).all()
            # Will return nothing if id is invalid
            return rides

    # Return all events from a given user
    def all_calendar_email(self, email):
        with app.app_context():
            rides = db.session.query(Calendar).filter_by(email=email).all()
            # Will return nothing if id is invalid
            return rides

    def all_calendar_date(self, ride_date: str):
        print(ride_date)
        with app.app_context():
            rides = db.session.query(Calendar).filter_by(date=ride_date).all()
            return rides


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
        cafe_choices.append(cafe.name)
    cafe_choices.append("new cafe")

    # ----------------------------------------------------------- #
    # Generate the list of routes
    # ----------------------------------------------------------- #
    gpx_choices = []
    gpxes = Gpx().all_gpxes()
    for gpx in gpxes:
        gpx_choices.append(f"{gpx.id}: '{gpx.name}', {gpx.length_km}km / {gpx.ascent_m}m")
    gpx_choices.append("upload my own route")

    # ----------------------------------------------------------- #
    # The form itself
    # ----------------------------------------------------------- #
    date = DateField("Which day is the ride for:", format='%d/%m/%Y', validators=[DataRequired()])
    leader = StringField("Ride Leader:", validators=[DataRequired()])
    destination = SelectField("Cafe:", choices=cafe_choices, validators=[DataRequired()])
    new_destination = StringField("If you're going to a new cafe, pray tell:", validators=[])
    group = SelectField("What pace is the ride:", choices=GROUP_CHOICES, validators=[DataRequired()])

    gpx_name = SelectField("Choose an existing route:", choices=gpx_choices, validators=[DataRequired()])
    gpx_file = FileField("or, upload your own GPX file:", validators=[])

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