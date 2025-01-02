# -------------------------------------------------------------------------------------------------------------- #
# Import out database connection from __init__
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Use these masks on the Integer to extract permissions
MASK_READ = 1


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Message Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class MessageModel(db.Model):  # type: ignore
    __tablename__ = 'messages'
    __table_args__ = {'schema': 'elsr'}

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    # Unique reference in dB
    id: int = db.Column(db.Integer, primary_key=True)

    # Contents of the message
    from_email: str = db.Column(db.String(250), unique=False)
    to_email: str = db.Column(db.String(250), unique=False)

    # Dates stored as "11112023"
    sent_date: str = db.Column(db.String(250), unique=False)
    read_date: str = db.Column(db.String(250), unique=False)

    # Actual message itself
    body: str = db.Column(db.String(1000), unique=False)

    # See above for details of how this works
    status: int = db.Column(db.Integer, unique=False)

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<Message from {self.from_email}, to {self.to_email}, on {self.sent_date}>'

    # ---------------------------------------------------------------------------------------------------------- #
    # Properties
    # ---------------------------------------------------------------------------------------------------------- #

    @property
    def been_read(self):
        """
        Property to help interpret the status value of the message.
        :return:    Returns True if the message has been read, False otherwise
        """
        try:
            return (self.status & MASK_READ) > 0
        except TypeError:  # Handles None or invalid types
            self.status = 0  # Reset status to 0
            return False
