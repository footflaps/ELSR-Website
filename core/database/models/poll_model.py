# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Poll Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class PollModel(db.Model):
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

    def __repr__(self):
        return f'<Poll "{self.name}, on {self.date}">'
