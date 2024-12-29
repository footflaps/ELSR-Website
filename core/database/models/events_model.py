# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Event Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class EventModel(db.Model):
    __tablename__ = 'events'
    __table_args__ = {'schema': 'elsr'}

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(50))

    # Use Unix epoch time (rounded to an Int)
    date = db.Column(db.Integer)

    type = db.Column(db.String(50))

    details = db.Column(db.String(500))

    def __repr__(self):
        return f'<Event "{self.details}">'

