from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, IntegerField, DateField, validators, HiddenField
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from datetime import datetime


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

POLL_PRIVATE = "Private"
POLL_PUBLIC = "Public"
POLL_NO_RESPONSE = ""
POLL_OPEN = "Open"
POLL_CLOSED = "Closed"

# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Poll Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class Polls(db.Model):
    __tablename__ = 'polls'
    __table_args__ = {'schema': 'elsr'}

    id = db.Column(db.Integer, primary_key=True)

    # Who created the entry - will determine delete permissions
    email = db.Column(db.String(50))

    # Use string for date eg '13012023'
    created_date = db.Column(db.String(8))

    # Use string for date eg '13012023'
    termination_date = db.Column(db.String(8))

    # Name of poll
    name = db.Column(db.Text)

    # Description
    details = db.Column(db.Text)

    # Options
    options = db.Column(db.Text)

    # Responses
    responses = db.Column(db.Text)

    # How many selections can be made
    max_selections = db.Column(db.Integer)

    # Privacy (Public / Private)
    privacy = db.Column(db.String(20))

    # Open / closed
    status = db.Column(db.String(8))

    def all(self):
        with app.app_context():
            polls = db.session.query(Polls).all()
            return polls

    def one_poll_by_id(self, poll_id):
        with app.app_context():
            poll = db.session.query(Polls).filter_by(id=poll_id).first()
            return poll

    def add_poll(self, new_poll):
        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_poll)
                db.session.commit()
                # Return social object
                return db.session.query(Polls).filter_by(id=new_poll.id).first()
            except Exception as e:
                app.logger.error(f"dB.add_poll(): Failed with error code '{e.args}'.")
                print(f"EdB.add_poll(): Failed with error code '{e.args}'.")
                return None

    def delete_poll(self, poll_id):
        with app.app_context():

            # Locate the GPX file
            poll = db.session.query(Polls).filter_by(id=poll_id).first()

            if poll:
                # Delete the GPX file
                try:
                    db.session.delete(poll)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_poll: Failed to delete Poll for poll_id = '{poll_id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    # Optional: this will allow each object to be identified by its details when printed.
    def __repr__(self):
        return f'<Poll "{self.name}, on {self.date}">'


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    db.create_all()


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                                WT Forms
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Custom validator for number entries (must be +ve integer)
# -------------------------------------------------------------------------------------------------------------- #
def selection_validation(form, field):
    if int(field.data) < 0:
        raise validators.ValidationError('Must be a positive integer!')


# -------------------------------------------------------------------------------------------------------------- #
# Custom validator for termination date (must be in the future)
# -------------------------------------------------------------------------------------------------------------- #
def date_validation(form, field):
    # This will be '<class 'datetime.date'>'
    today_date = datetime.today().date()
    # This can be either  '<class 'datetime.date'>' or '<class 'datetime.datetime'>'
    poll_date = field.data
    # Convert to date object as we can't compare date vs datetime
    if type(poll_date) == datetime:
        poll_date = poll_date.date()
    # Might not be set...
    if poll_date:
        if poll_date < today_date:
            raise validators.ValidationError('Poll must end in the future!')


# -------------------------------------------------------------------------------------------------------------- #
# Create Poll Form
# -------------------------------------------------------------------------------------------------------------- #
def create_poll_form(edit: bool):
    class Form(FlaskForm):
        name = StringField("What is the name of the poll?", validators=[InputRequired("Please enter a name.")])
        details = CKEditorField("Provide some details:",
                                validators=[InputRequired("Please enter some vague idea about the poll.")])
        options = CKEditorField("Enter the options as Bullet Point List:",
                                validators=[InputRequired("Please enter some options.")])
        termination_date = DateField("When does the poll finish?", format='%Y-%m-%d', validators=[date_validation])
        max_selections = IntegerField("How many options can the user choose? (0 = all)",
                                      validators=[InputRequired("Please enter a number."), selection_validation])
        privacy = SelectField("Is this poll Public or Private:",
                              choices=[POLL_PUBLIC, POLL_PRIVATE], validators=[])
        status = SelectField("Is this poll still open or has it finished (closed)?",
                             choices=[POLL_OPEN, POLL_CLOSED], validators=[])
        poll_id = HiddenField("poll_id")

        cancel = SubmitField("Cancel")
        update = SubmitField("Update")
        submit = SubmitField("Submit")

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
    polls = db.session.query(Polls).all()
    print(f"Found {len(polls)} polls in the dB")
    app.logger.debug(f"Start of day: Found {len(polls)} polls in the dB")
