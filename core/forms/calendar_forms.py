from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField, validators, TimeField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired
import os
from datetime import datetime


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import GPX_UPLOAD_FOLDER_ABS
from core.database.repositories.cafe_repository import CafeRepository
from core.database.repositories.gpx_repository import GpxRepository
from core.database.repositories.user_repository import UserRepository
from core.database.repositories.calendar_repository import MEETING_OTHER, NEW_CAFE, UPLOAD_ROUTE, GROUP_CHOICES, MEETING_CHOICES


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
        cafes = CafeRepository().all_cafes_sorted()
        for cafe in cafes:
            cafe_choices.append(cafe.combo_string())
        cafe_choices.append(NEW_CAFE)

        # ----------------------------------------------------------- #
        # Generate the list of routes
        # ----------------------------------------------------------- #
        gpx_choices = [UPLOAD_ROUTE]
        gpxes = GpxRepository().all_gpxes_sorted()
        for gpx in gpxes:
            filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
            # Route must be public and double check we have an actual GPX file on tap....
            if (gpx.public and os.path.exists(filename)) \
                    or gpx.id == gpx_id:
                gpx_choices.append(gpx.combo_string())

        # ----------------------------------------------------------- #
        # Generate the list of users
        # ----------------------------------------------------------- #
        users = UserRepository().all_users_sorted()
        all_users = []
        for user in users:
            all_users.append(user.combo_str)

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

