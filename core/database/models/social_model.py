# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Social Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class SocialModel(db.Model):
    __tablename__ = 'socials'
    __table_args__ = {'schema': 'elsr'}

    id = db.Column(db.Integer, primary_key=True)

    # Organiser
    organiser = db.Column(db.String(50))

    # Who created the entry - will determine delete permissions
    email = db.Column(db.String(50))

    # Use string for date eg '13012023'
    date = db.Column(db.String(8))

    # New date column using a proper SQL Date field
    converted_date = db.Column(db.Date)

    # Destination cafe eg 'Mill End Plants'
    destination = db.Column(db.String(100))

    # Details
    details = db.Column(db.String(1000))

    # Start time
    start_time = db.Column(db.String(20))

    # Privacy (Public / Private)
    privacy = db.Column(db.String(20))

    # Allow people to sign up (True / False)
    sign_up = db.Column(db.String(8))

    # JSON string of emails of attendees
    attendees = db.Column(db.Text)

    def __repr__(self):
        return f'<Social "{self.destination}, on {self.date}">'
