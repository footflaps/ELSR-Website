from flask_login import UserMixin
import hashlib


# -------------------------------------------------------------------------------------------------------------- #
# Import out database connection from __init__
# -------------------------------------------------------------------------------------------------------------- #

from core import db, GROUP_NOTIFICATIONS


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# User().permissions is an Integer value with binary breakdown:
#       1 :     Admin                   1 = Admin,          0 = Normal user
#       2 :     Verified                1 = Verified,       0 = Unverified
#       4 :     Blocked                 1 = Active,         0 = Blocked by Admin
#       8 :     Read/Write              1 = Read+Write,     0 = Read only

# Use these masks on the Integer to extract permissions
MASK_ADMIN = 1
MASK_VERIFIED = 2
MASK_BLOCKED = 4
MASK_READWRITE = 8

# We prefix unverified phone numbers with this code
UNVERIFIED_PHONE_PREFIX = "uv"

# Notifications
NOTIFICATIONS_DEFAULT_VALUE = 0
MESSAGE_NOTIFICATION = "When I receive a message"
SOCIAL_NOTIFICATION = "When someone posts a social"
BLOG_NOTIFICATION = "When someone posts a blog entry"


NOTIFICATIONS = [
        {"name": MESSAGE_NOTIFICATION,
         "mask": 2},
        {"name": GROUP_NOTIFICATIONS[2],
         "mask": 4},
        {"name": GROUP_NOTIFICATIONS[1],
         "mask": 8},
        {"name": GROUP_NOTIFICATIONS[0],
         "mask": 16},
        {"name": GROUP_NOTIFICATIONS[3],
         "mask": 32},
        {"name": SOCIAL_NOTIFICATION,
         "mask": 64},
        {"name": BLOG_NOTIFICATION,
         "mask": 128},
]


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

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

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

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<User {self.name} ({self.email})>'

    # ---------------------------------------------------------------------------------------------------------- #
    # Properties
    # ---------------------------------------------------------------------------------------------------------- #

    @property
    def admin(self):
        if self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    @property
    def verified(self):
        if self.permissions & MASK_VERIFIED > 0 or \
           self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    @property
    def blocked(self):
        if self.permissions & MASK_BLOCKED > 0:
            return True
        else:
            return False

    @property
    def readwrite(self):
        if self.permissions & MASK_READWRITE > 0 or \
           self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    @property
    def can_see_emergency_contacts(self):
        # For now, we just use Admin, but will probably expand this to other members
        return self.admin

    @property
    def combo_str(self):
        return f"{self.name} ({self.id})"

    @property
    def unsubscribe_code(self):
        # Need something secret, that no one else would know, so hash their password hash
        return hashlib.md5(f"{self.password}".encode('utf-8')).hexdigest()

    @property
    def has_valid_phone_number(self):
        if not self.phone_number:
            return False
        # Check for UK code
        elif self.phone_number[0:3] != "+44":
            return False
        # Check valid length ('+' and 12 digits)
        if len(self.phone_number) != 13:
            return False
        # Looks OK
        return True

    @property
    def has_unvalidated_phone_number(self):
        if not self.phone_number:
            return False
        # Check for UK code
        elif self.phone_number[0:3+len(UNVERIFIED_PHONE_PREFIX)] != UNVERIFIED_PHONE_PREFIX + "+44":
            return False
        # Check valid length ('+' and 12 digits)
        if len(self.phone_number) != len(UNVERIFIED_PHONE_PREFIX) + 13:
            return False
        # Looks OK
        return True

    @property
    def notification_choices_set(self):
        # Handle unset as new column
        if not self.notifications:
            self.notifications = 0
        # Return this
        user_choices = []
        # Loop through our set
        for notification in NOTIFICATIONS:
            name = notification['name']
            mask = notification['mask']
            user_choices.append({
                "name": name,
                "status": self.notifications & mask > 0
            })
        return user_choices
