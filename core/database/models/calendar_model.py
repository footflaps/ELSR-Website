from datetime import date as date_type

# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Calendar Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class CalendarModel(db.Model):  # type: ignore
    __tablename__ = 'calendar'
    __table_args__ = {'schema': 'elsr'}

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    id: int = db.Column(db.Integer, primary_key=True)

    # Who created the entry - will determine delete permissions
    email: str = db.Column(db.String(50))

    # Use string for date eg '13012023'
    date: str = db.Column(db.String(8))

    # New date column using a proper SQL Date field
    converted_date: date_type = db.Column(db.Date)

    # Ride group eg 'Decaf', 'Doppio' etc
    group: str = db.Column(db.String(20))

    # Ride leader
    leader: str = db.Column(db.String(25))

    # Destination cafe eg 'Mill End Plants'
    destination: str = db.Column(db.String(200))

    # GPX ID, the route will exist in the gpx dB
    gpx_id: int = db.Column(db.Integer)

    # Cafe ID, the cafe might exist in the Cafe dB (could be a new cafe)
    cafe_id: int = db.Column(db.Integer)

    # Start time
    start_time: str = db.Column(db.String(250))

    # Added Unix date for sorting by ride date
    unix_date: int = db.Column(db.Integer)

    # Column to denote whether we sent an email or not
    sent_email: str = db.Column(db.String(20))

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<Ride "{self.destination} , lead by {self.leader}">'

