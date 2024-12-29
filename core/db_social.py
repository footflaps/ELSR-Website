from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField, TimeField, validators
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from datetime import datetime


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db
from core.database.models.socials_model import SocialsModel


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# These are in the form and can change
SOCIAL_FORM_PRIVATE = "Private (Regular riders only)"
SOCIAL_FORM_PUBLIC = "Public (Anyone on the internet)"
# Don't change these as they are in the db
SOCIAL_DB_PRIVATE = "PRIVATE"
SOCIAL_DB_PUBLIC = "PUBLIC"
SIGN_UP_YES = "Absolutely"
SIGN_UP_NO = "I just don't care"
SIGN_UP_CHOICES = [SIGN_UP_NO, SIGN_UP_YES]


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Social Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class Socials(SocialsModel):

    # Return all socials
    def all(self):
        with app.app_context():
            socials = db.session.query(Socials).all()
            return socials

    def all_by_email(self, email):
        with app.app_context():
            socials = db.session.query(Socials).filter_by(email=email).all()
            return socials

    def one_social_id(self, social_id):
        with app.app_context():
            social = db.session.query(Socials).filter_by(id=social_id).first()
            return social

    def add_social(self, new_social):
        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_social)
                db.session.commit()
                # Return social object
                return db.session.query(Socials).filter_by(id=new_social.id).first()
            except Exception as e:
                app.logger.error(f"dB.add_social(): Failed with error code '{e.args}'.")
                return None

    def delete_social(self, social_id):
        with app.app_context():

            # Locate the GPX file
            social = db.session.query(Socials).filter_by(id=social_id).first()

            if social:
                # Delete the GPX file
                try:
                    db.session.delete(social)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_social: Failed to delete Social for social_id = '{social_id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    def all_socials_date(self, date_str: str):
        with app.app_context():
            socials = db.session.query(Socials).filter_by(date=date_str).all()
            for social in socials:
                date_str = social.date
                social_date = datetime(int(date_str[4:8]), int(date_str[2:4]), int(date_str[0:2]), 0, 00).date()
                social.long_date = social_date.strftime("%A %b %d %Y")
            return socials

    def all_socials_future(self):
        socials = []
        today = datetime.today().date()
        all_socials = self.all()
        for social in all_socials:
            date_str = social.date
            social_date = datetime(int(date_str[4:8]), int(date_str[2:4]), int(date_str[0:2]), 0, 00).date()
            # Either today or in the future
            if social_date >= today:
                social.long_date = social_date.strftime("%A %b %d %Y")
                socials.append(social)
        return socials


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

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
    social_date = field.data
    # Convert to date object as we can't compare date vs datetime
    if type(social_date) == datetime:
        social_date = social_date.date()
    # Might not be set...
    if social_date:
        if social_date < today_date:
            raise validators.ValidationError("The date is in the past!")


# -------------------------------------------------------------------------------------------------------------- #
# Form itself
# -------------------------------------------------------------------------------------------------------------- #

def create_social_form(admin: bool):

    class Form(FlaskForm):

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
        date = DateField("Which day is the social for:", format='%Y-%m-%d',
                         validators=[date_validation])
        start_time = TimeField("Start time:", format="%H:%M")

        # Admin can assign to any user
        if admin:
            owner = SelectField("Owner (Admin only field):", choices=all_users,
                                validators=[InputRequired("Please enter an owner.")])

        organiser = StringField("Organiser:",
                                validators=[InputRequired("Please enter an organiser.")])

        destination = StringField("Location (can be hidden):",
                                  validators=[InputRequired("Please enter a destination.")])

        destination_hidden = SelectField("Social type:",
                                         choices=[SOCIAL_FORM_PRIVATE, SOCIAL_FORM_PUBLIC],
                                         validators=[])

        details = CKEditorField("When, where, dress code etc:",
                                validators=[InputRequired("Please provide some details.")])

        sign_up = SelectField("Do you *need* people to sign up?",
                              choices=SIGN_UP_CHOICES,
                              validators=[])

        cancel = SubmitField("Maybe not")
        submit = SubmitField("Go for it!")

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
    rides = db.session.query(Socials).all()
    print(f"Found {len(rides)} socials in the dB")
    app.logger.debug(f"Start of day: Found {len(rides)} socials in the dB")

