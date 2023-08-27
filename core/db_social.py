from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from datetime import datetime


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Social Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class Socials(db.Model):
    # We're using multiple dBs with one instance of SQLAlchemy, so have to bind to the right one.
    __bind_key__ = 'socials'

    id = db.Column(db.Integer, primary_key=True)

    # Organiser
    organiser = db.Column(db.String(50))

    # Who created the entry - will determine delete permissions
    email = db.Column(db.String(50))

    # Use string for date eg '13012023'
    date = db.Column(db.String(8))

    # Destination cafe eg 'Mill End Plants'
    destination = db.Column(db.String(50))

    # Details
    details = db.Column(db.String(500))

    # Return all events
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
                # Return success
                return True
            except Exception as e:
                app.logger.error(f"dB.add_social(): Failed with error code '{e.args}'.")
                return False

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

    # Optional: this will allow each event object to be identified by its details when printed.
    def __repr__(self):
        return f'<Social "{self.destination}, on {self.date}">'


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

class CreateSocialForm(FlaskForm):

    # ----------------------------------------------------------- #
    # The form itself
    # ----------------------------------------------------------- #
    date = DateField("Which day is the social for:", format='%Y-%m-%d', validators=[])
    organiser = StringField("Organiser:", validators=[InputRequired("Please enter an organiser.")])
    destination = StringField("Location:", validators=[InputRequired("Please enter a destination.")])
    details = CKEditorField("When, where, dress code etc:", validators=[InputRequired("Please provide some details.")])

    cancel = SubmitField("Maybe not")
    submit = SubmitField("Go for it!")


class AdminCreateSocialForm(FlaskForm):

    # ----------------------------------------------------------- #
    # Generate the list of users
    # ----------------------------------------------------------- #

    users = User().all_users()
    all_users = []
    for user in users:
        all_users.append(user.combo_str())

    # ----------------------------------------------------------- #
    # The form itself
    # ----------------------------------------------------------- #
    date = DateField("Which day is the social for:", format='%Y-%m-%d', validators=[])
    owner = SelectField("Owner (Admin only field):", choices=all_users, validators=[InputRequired("Please enter an owner.")])
    organiser = StringField("Organiser:", validators=[InputRequired("Please enter an organiser.")])
    destination = StringField("Location:", validators=[InputRequired("Please enter a destination.")])
    details = CKEditorField("When, where, dress code etc:", validators=[InputRequired("Please provide some details.")])

    cancel = SubmitField("Maybe not")
    submit = SubmitField("Go for it!")


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