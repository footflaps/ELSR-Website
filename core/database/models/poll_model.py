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

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    id: int = db.Column(db.Integer, primary_key=True)

    # Who created the entry - will determine delete permissions
    email: str = db.Column(db.String(50))

    # Use string for date eg '13012023'
    created_date: str = db.Column(db.String(8))

    # Use string for date eg '13012023'
    termination_date: str = db.Column(db.String(8))

    # Name of poll
    name: str = db.Column(db.Text)

    # Description
    details: str = db.Column(db.Text)

    # Options
    options: str = db.Column(db.Text)

    # Responses
    responses: str = db.Column(db.Text)

    # How many selections can be made
    max_selections: int = db.Column(db.Integer)

    # Privacy (Public / Private)
    privacy: str = db.Column(db.String(20))

    # Open / closed
    status: str = db.Column(db.String(8))

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<Poll "{self.name}, on {self.date}">'
