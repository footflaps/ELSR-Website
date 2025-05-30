# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Event Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class EventModel(db.Model):  # type: ignore
    __tablename__ = 'events'
    __table_args__ = {'schema': 'elsr'}

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    id: int = db.Column(db.Integer, primary_key=True)

    email: str = db.Column(db.String(50))

    # Use Unix epoch time (rounded to an Int)
    date: int = db.Column(db.Integer)

    type: str = db.Column(db.String(50))

    details: str = db.Column(db.String(500))

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<Event "{self.details}">'

