from flask_login import UserMixin
import hashlib
from typing import Any
import json


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


NOTIFICATIONS: list[dict[str, Any]] = [
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

class UserModel(UserMixin, db.Model):   # type: ignore
    # ---------------------------------------------------------------------------------------------------------- #
    # Define the SQL Table
    # ---------------------------------------------------------------------------------------------------------- #
    __tablename__ = 'users'
    __table_args__ = {'schema': 'elsr'}

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    # Unique references
    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email: str = db.Column(db.String(100), unique=True)

    # Name is user defined string, we enforce uniqueness ourselves
    name: str = db.Column(db.String(1000), unique=False)

    # Password in hashed checksum
    password: str = db.Column(db.String(100), unique=False)

    # When they signed up
    start_date: str = db.Column(db.String(100), unique=False)

    # Tracking usage - last_login is of the form "02/10/2023 10:30:53"
    last_login: str = db.Column(db.String(100), unique=False)
    last_login_ip: str = db.Column(db.String(100), unique=False)

    # User permission code, see above for details of how this works
    permissions: int = db.Column(db.Integer, unique=False)

    # In case we have to record stuff about a user
    admin_notes: str = db.Column(db.String(1000), unique=False)

    # For verifying email address, we have a code and an expiry time (Unix Epoch)
    verification_code = db.Column(db.Integer, unique=False)
    verification_code_timestamp = db.Column(db.Integer, unique=False)

    # For resetting password, we have a code and an expiry time (Unix Epoch)
    reset_code: int = db.Column(db.Integer, unique=False)
    reset_code_timestamp: int = db.Column(db.Integer, unique=False)

    # Phone number
    phone_number: str = db.Column(db.String(25), unique=False)

    # User Notifications code, see above for details of how this works
    notifications: int = db.Column(db.Integer, unique=False)

    # They can store social media handles as JSON string
    socials: str = db.Column(db.Text, unique=False)

    # A short biography
    bio: str = db.Column(db.Text, unique=False)

    # They can store club kit clothing sizes as JSON string
    clothing_size: str = db.Column(db.Text, unique=False)

    # Emergency Contact Details
    emergency_contacts: str = db.Column(db.Text, unique=False)

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<User {self.name} ({self.email})>'

    # ---------------------------------------------------------------------------------------------------------- #
    # Properties
    # ---------------------------------------------------------------------------------------------------------- #

    @property
    def admin(self) -> bool:
        if self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    @property
    def verified(self) -> bool:
        if self.permissions & MASK_VERIFIED > 0 or \
           self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    @property
    def blocked(self) -> bool:
        if self.permissions & MASK_BLOCKED > 0:
            return True
        else:
            return False

    @property
    def readwrite(self) -> bool:
        if self.permissions & MASK_READWRITE > 0 or \
           self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    @property
    def can_see_emergency_contacts(self) -> bool:
        # For now, we just use Admin, but will probably expand this to other members
        return self.admin

    @property
    def combo_str(self) -> str:
        return f"{self.name} ({self.id})"

    @property
    def unsubscribe_code(self) -> str:
        # Need something secret, that no one else would know, so hash their password hash
        return hashlib.md5(f"{self.password}".encode('utf-8')).hexdigest()

    @property
    def has_valid_phone_number(self) -> bool:
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
    def has_unvalidated_phone_number(self) -> bool:
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
    def notification_choices_set(self) -> list[dict[str, Any]]:
        # Handle unset as new column
        if not self.notifications:
            self.notifications = 0
        # Return this
        user_choices: list[dict[str, Any]] = []
        # Loop through our set
        for notification in NOTIFICATIONS:
            name: str = notification['name']
            mask: int = notification['mask']
            user_choices.append({
                "name": name,
                "status": bool(self.notifications & mask > 0)
            })
        return user_choices

    def gpx_download_code(self, gpx_id: int) -> str:
        # Need something secret, that no one else would know, so hash their password hash
        return hashlib.md5(f"{self.password}{gpx_id}".encode('utf-8')).hexdigest()

    def social_url(self, social: str) -> str:
        """
        Extract the specific social URL for a  given 'social' category eg 'facebook'
        :param social:              The social category to extract eg 'facebook'
        :return:                    The URL eg "facebook.com/my_username"
        """
        if not self.socials:
            return "n/a"
        try:
            return json.loads(self.socials)[social]
        except KeyError:
            return "n/a"
