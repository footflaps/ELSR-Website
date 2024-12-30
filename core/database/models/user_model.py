from flask_login import UserMixin

# -------------------------------------------------------------------------------------------------------------- #
# Import out database connection from __init__
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define User Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class UserModel(UserMixin, db.Model):
    # ---------------------------------------------------------------------------------------------------------- #
    # Define the SQL Table
    # ---------------------------------------------------------------------------------------------------------- #
    __tablename__ = 'users'
    __table_args__ = {'schema': 'elsr'}

    # Unique references
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(100), unique=True)

    # Name is user defined string, we enforce uniqueness ourselves
    name = db.Column(db.String(1000), unique=False)

    # Password in hashed checksum
    password = db.Column(db.String(100), unique=False)

    # When they signed up
    start_date = db.Column(db.String(100), unique=False)

    # Tracking usage - last_login is of the form "02/10/2023 10:30:53"
    last_login = db.Column(db.String(100), unique=False)
    last_login_ip = db.Column(db.String(100), unique=False)

    # User permission code, see above for details of how this works
    permissions = db.Column(db.Integer, unique=False)

    # In case we have to record stuff about a user
    admin_notes = db.Column(db.String(1000), unique=False)

    # For verifying email address, we have a code and an expiry time (Unix Epoch)
    verification_code = db.Column(db.Integer, unique=False)
    verification_code_timestamp = db.Column(db.Integer, unique=False)

    # For resetting password, we have a code and an expiry time (Unix Epoch)
    reset_code = db.Column(db.Integer, unique=False)
    reset_code_timestamp = db.Column(db.Integer, unique=False)

    # Phone number
    phone_number = db.Column(db.String(25), unique=False)

    # User Notifications code, see above for details of how this works
    notifications = db.Column(db.Integer, unique=False)

    # They can store social media handles as JSON string
    socials = db.Column(db.Text, unique=False)

    # A short biography
    bio = db.Column(db.Text, unique=False)

    # They can store club kit clothing sizes as JSON string
    clothing_size = db.Column(db.Text, unique=False)

    # Emergency Contact Details
    emergency_contacts = db.Column(db.Text, unique=False)

    def __repr__(self):
        return f'<User {self.name} ({self.email})>'

