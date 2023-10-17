from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, IntegerField
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from datetime import datetime


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Poll Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class Polls(db.Model):
    # We're using multiple dBs with one instance of SQLAlchemy, so have to bind to the right one.
    __bind_key__ = 'polls'

    id = db.Column(db.Integer, primary_key=True)

    # Who created the entry - will determine delete permissions
    email = db.Column(db.String(50))

    # Use string for date eg '13012023'
    date = db.Column(db.String(8))

    # Name of poll
    name = db.Column(db.Text)

    # Description
    details = db.Column(db.Text)

    # Options
    options = db.Column(db.Text)

    # How many selections can be made
    max_selections = db.Column(db.Integer)

    # Privacy (Public / Private)
    privacy = db.Column(db.String(20))

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
# Create Poll Form
# -------------------------------------------------------------------------------------------------------------- #
class CreatePollForm(FlaskForm):
    name = StringField("What is the name of the poll?", validators=[InputRequired("Please enter a name.")])
    details = CKEditorField("Provide some details:",
                            validators=[InputRequired("Please enter some vague idea about the poll.")])
    options = StringField("Enter the options as a Comma Separated List eg Monday, Tuesday, Wednesday:",
                          validators=[InputRequired("Please enter some options.")])
    max_selections = IntegerField("How many options can the user choose? (0 = all)",
                                  validators=[InputRequired("Please enter a number.")])
    privacy = SelectField("Is this poll Public or Private:",
                          choices=["Private", "Public"], validators=[])
    submit = SubmitField("Save")


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

