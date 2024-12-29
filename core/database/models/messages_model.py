# -------------------------------------------------------------------------------------------------------------- #
# Import out database connection from __init__
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# Define Message
# -------------------------------------------------------------------------------------------------------------- #

class MessageModel(db.Model):
    __tablename__ = 'messages'
    __table_args__ = {'schema': 'elsr'}

    # Unique reference in dB
    id = db.Column(db.Integer, primary_key=True)

    # Contents of the message
    from_email = db.Column(db.String(250), unique=False)
    to_email = db.Column(db.String(250), unique=False)

    # Dates stored as "11112023"
    sent_date = db.Column(db.String(250), unique=False)
    read_date = db.Column(db.String(250), unique=False)

    # Actual message itself
    body = db.Column(db.String(1000), unique=False)

    # See above for details of how this works
    status = db.Column(db.Integer, unique=False)

    def __repr__(self):
        return f'<Message from {self.from_email}, to {self.to_email}, on {self.sent_date}>'

