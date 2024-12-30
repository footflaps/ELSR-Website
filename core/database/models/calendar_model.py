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

class CalendarModel(db.Model):
    __tablename__ = 'calendar'
    __table_args__ = {'schema': 'elsr'}

    id = db.Column(db.Integer, primary_key=True)

    # Who created the entry - will determine delete permissions
    email = db.Column(db.String(50))

    # Use string for date eg '13012023'
    date = db.Column(db.String(8))

    # New date column using a proper SQL Date field
    converted_date = db.Column(db.Date)

    # Ride group eg 'Decaf', 'Doppio' etc
    group = db.Column(db.String(20))

    # Ride leader
    leader = db.Column(db.String(25))

    # Destination cafe eg 'Mill End Plants'
    destination = db.Column(db.String(200))

    # GPX ID, the route will exist in the gpx dB
    gpx_id = db.Column(db.Integer)

    # Cafe ID, the cafe might exist in the Cafe dB (could be a new cafe)
    cafe_id = db.Column(db.Integer)

    # Start time
    start_time = db.Column(db.String(250))

    # Added Unix date for sorting by ride date
    unix_date = db.Column(db.Integer)

    # Column to denote whether we sent an email or not
    sent_email = db.Column(db.String(20))

    def __repr__(self):
        return f'<Ride "{self.destination} , lead by {self.leader}">'

