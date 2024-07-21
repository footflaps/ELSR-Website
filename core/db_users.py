# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define the user table in the database and associated helper functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
from flask import abort, flash, request, redirect, url_for
from flask_login import UserMixin, current_user, logout_user
from flask_wtf import FlaskForm
from flask_ckeditor import CKEditorField
from wtforms import StringField, EmailField, SubmitField, PasswordField, IntegerField, URLField, SelectField, validators
from wtforms.validators import InputRequired, Email
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import time
from datetime import date, datetime
import random
import os
import hashlib
from sqlalchemy import func
import json
from validators import url as check_url


# -------------------------------------------------------------------------------------------------------------- #
# Import out database connection from __init__
# -------------------------------------------------------------------------------------------------------------- #

from core import db, app, login_manager, GROUP_CHOICES, GROUP_NOTIFICATIONS


# -------------------------------------------------------------------------------------------------------------- #
# We need Messages & Events
# -------------------------------------------------------------------------------------------------------------- #

from core.db_messages import Message
from core.dB_events import Event


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

# Default User Permissions on verification
DEFAULT_PERMISSIONS_VALUE = 0

# One day time out for email
VERIFICATION_TIMEOUT_SECS = 60 * 60 * 24
RESET_TIMEOUT_SECS = 60 * 60 * 24

# 15 min time out for SMS
SMS_VERIFICATION_TIMEOUT_SECS = 60 * 15

# Protected users (can't be deleted)
PROTECTED_USERS = os.environ['ELSR_PROTECTED_USERS']

# This is the only user who can do things like make / unmake Admins (to stop another Admin locking me out)
SUPER_ADMIN_USER_ID = 1

# Num digits for Verification / Password Reset Codes
NUM_DIGITS_CODES = 6

# We prefix unverified phone numbers with this code
UNVERIFIED_PHONE_PREFIX = "uv"

# For soft deleting users, we change their name to
DELETED_NAME = "DELETED"

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

# Sizes for club kit
SIZES = ["unset", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL"]


# -------------------------------------------------------------------------------------------------------------- #
# User loader function
# -------------------------------------------------------------------------------------------------------------- #

# You will need to provide a user_loader callback. This callback is used to reload the user object from the user
# ID stored in the session. It should take the str ID of a user, and return the corresponding user object.
# Fix for Gunicorn and multiple servers running in parallel
# See https://stackoverflow.com/questions/39684364/heroku-gunicorn-flask-login-is-not-working-properly

@login_manager.user_loader
def load_user(user_id):
    # Only log user details on the webserver
    # if os.path.exists("/home/ben_freeman_eu/elsr_website/ELSR-Website/env_vars.py"):
    #     app.logger.debug(f"session = '{session}', user_id = '{user_id}'")
    return User.query.get(int(user_id))


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                              Define User
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class User(UserMixin, db.Model):
    # ---------------------------------------------------------------------------------------------------------- #
    # Define the SQL Table
    # ---------------------------------------------------------------------------------------------------------- #

    # We're using multiple dBs with one instance of SQLAlchemy, so have to bind to the right one.
    __bind_key__ = 'users'

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
    # User permissions
    # ---------------------------------------------------------------------------------------------------------- #

    def admin(self):
        if self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    def verified(self):
        if self.permissions & MASK_VERIFIED > 0 or \
           self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    def blocked(self):
        if self.permissions & MASK_BLOCKED > 0:
            return True
        else:
            return False

    def readwrite(self):
        if self.permissions & MASK_READWRITE > 0 or \
           self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    def has_mail(self):
        if Message().all_unread_messages_to_email(self.email):
            return True
        else:
            return False

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

    def notification_choice(self, chosen_name):
        # Handle unset as new column
        if not self.notifications:
            self.notifications = 0
        # Loop through our set
        for notification in NOTIFICATIONS:
            name = notification['name']
            mask = notification['mask']
            if name == chosen_name:
                return self.notifications & mask
        return False

    def social_url(self, social):
        if not self.socials:
            return ""
        try:
            return json.loads(self.socials)[social]
        except KeyError:
            return "n/a"

    def can_see_emergency_contacts(self):
        # For now, we just use Admin, but will probably expand this to other members
        return self.admin()

    # ---------------------------------------------------------------------------------------------------------- #
    # User functions
    # ---------------------------------------------------------------------------------------------------------- #

    @staticmethod
    def all_users():
        with app.app_context():
            users = db.session.query(User).filter(User.name != DELETED_NAME).all()
            return users

    @staticmethod
    def all_users_sorted():
        with app.app_context():
            users = db.session.query(User).order_by(func.lower(User.name)).filter(User.name != DELETED_NAME).all()
            return users

    @staticmethod
    def all_admins():
        with app.app_context():
            admins = db.session.query(User).filter(User.permissions == MASK_ADMIN + MASK_VERIFIED).all()
            return admins

    @staticmethod
    def all_non_admins():
        with app.app_context():
            non_admins = db.session.query(User).filter(User.permissions != MASK_ADMIN + MASK_VERIFIED).\
                filter(User.name != DELETED_NAME).all()
            return non_admins

    def create_user(self, new_user, raw_password):
        # Hash password before adding to dB
        new_user.password = self.hash_password(raw_password)

        # By default new users are not verified and have no permissions until verified
        new_user.verification_code = random_code(NUM_DIGITS_CODES)
        new_user.verification_code_timestamp = time.time()
        new_user.start_date = date.today().strftime("%d%m%Y")
        new_user.permissions = DEFAULT_PERMISSIONS_VALUE
        new_user.notifications = NOTIFICATIONS_DEFAULT_VALUE
        app.logger.debug(f"db.create_user(): User '{new_user.email}' issued with code '{new_user.verification_code}'.")

        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_user)
                db.session.commit()
                # Return success
                return True
            except Exception as e:
                app.logger.error(f"dB.create_user(): Failed with error code '{e.args}'.")
                return False

    @staticmethod
    def create_new_verification(user_id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                try:
                    user.verification_code = random_code(NUM_DIGITS_CODES)
                    user.verification_code_timestamp = time.time()
                    app.logger.debug(f"dB.create_new_verification(): User '{user.email}' "
                                     f"issued with code '{user.verification_code}'")
                    # Write to dB
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.create_new_verification(): Failed with error code '{e.args}' "
                                     f"for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.create_new_verification(): Called with invalid user_id = '{user_id}'.")
        return False

    @staticmethod
    def generate_sms_code(user_id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                try:
                    user.verification_code = random_code(NUM_DIGITS_CODES)
                    user.verification_code_timestamp = time.time()
                    app.logger.debug(f"dB.generate_sms_code(): User '{user.email}' "
                                     f"issued with code '{user.verification_code}'")
                    # Write to dB
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.generate_sms_code(): Failed with error code '{e.args}' "
                                     f"for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.generate_sms_code(): Called with invalid user_id = '{user_id}'.")
        return False

    @staticmethod
    def find_user_from_id(user_id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()
            return user

    def check_name_in_use(self, name):
        users = self.all_users()
        for user in users:
            if name.strip().lower() == user.name.strip().lower():
                return True
        return False

    @staticmethod
    def find_user_from_email(email):
        with app.app_context():
            user = db.session.query(User).filter_by(email=email).first()
            return user

    @staticmethod
    def find_id_from_email(email):
        with app.app_context():
            user = db.session.query(User).filter_by(email=email).first()
            if user:
                return user.id
            else:
                return None

    def display_name(self, email):
        with app.app_context():
            user = self.find_user_from_email(email)
            if user:
                return user.name
            else:
                return "unknown"

    @staticmethod
    def name_from_id(id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=id).first()
            return user.name

    def hash_password(self, raw_password):
        return generate_password_hash(raw_password, method='pbkdf2:sha256', salt_length=8)

    def validate_password(self, user, raw_password, user_ip):
        with app.app_context():
            if user.password:
                if check_password_hash(user.password, raw_password):
                    try:
                        # Update last login details
                        user = db.session.query(User).filter_by(id=user.id).first()
                        user.last_login = str(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
                        user.last_login_ip = str(user_ip)
                        db.session.commit()
                        return True
                    except Exception as e:
                        app.logger.error(f"dB.validate_password(): Failed with error code '{e.args}'.")
                        return False
            else:
                app.logger.error(f"dB.validate_password(): Called for user without password, user.id = '{user.id}'.")
                return False
        return False

    def log_activity(self, user_id):
        with app.app_context():
            try:
                user = db.session.query(User).filter_by(id=user_id).first()
                user.last_login = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                db.session.commit()
                return True
            except Exception as e:
                app.logger.error(f"dB.log_activity(): Failed with error code '{e.args}'.")
                return False

    def validate_email(self, user, code):
        with app.app_context():

            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(id=user.id).first()
            now = time.time()

            # Debug
            app.logger.debug(f"dB.validate_email(): Verifying user.id = '{user.id}', user.email = '{user.email}'")
            app.logger.debug(f"dB.validate_email(): Received code = '{code}', "
                             f"user.verification_code = '{user.verification_code}'")
            app.logger.debug(f"dB.validate_email(): user.verification_code_timestamp = "
                             f"'{user.verification_code_timestamp}', now = '{now}'")

            # Has the code timed out
            if now - user.verification_code_timestamp > VERIFICATION_TIMEOUT_SECS:
                # Code has time out
                app.logger.debug(f"dB.validate_email(): Verification code has timed out, user.email = '{user.email}'.")
                return False

            if int(code) == int(user.verification_code):
                user.permissions = user.permissions \
                                   | MASK_VERIFIED \
                                   | DEFAULT_PERMISSIONS_VALUE

                # Clear verification data, so it can't be used again
                user.verification_code = int(0)
                user.verification_code_timestamp = 0

                # Commit to dB
                try:
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.validate_email(): Failed with error code '{e.args}'.")
                    return False

            else:
                app.logger.debug(f"dB.validate_email(): Verification code doesn't match, user.email = '{user.email}'.")
                return False

    def validate_sms(self, user, code):
        with app.app_context():

            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(id=user.id).first()
            now = time.time()

            # Debug
            app.logger.debug(f"dB.validate_sms(): Verifying user.id = '{user.id}', user.email = '{user.email}'")
            app.logger.debug(f"dB.validate_sms(): Received code = '{code}', "
                             f"user.verification_code = '{user.verification_code}'")
            app.logger.debug(f"dB.validate_sms(): user.verification_code_timestamp = "
                             f"'{user.verification_code_timestamp}', now = '{now}'")

            # Has the code timed out
            if now - user.verification_code_timestamp > SMS_VERIFICATION_TIMEOUT_SECS:
                # Code has time out
                app.logger.debug(f"dB.validate_email(): Verification code has timed out, user.email = '{user.email}'.")
                return False

            if int(code) == int(user.verification_code):
                # Clear verification data, so it can't be used again
                user.verification_code = int(0)
                user.verification_code_timestamp = 0

                # Remove prefix from phone number
                if user.phone_number[0:len(UNVERIFIED_PHONE_PREFIX)] == UNVERIFIED_PHONE_PREFIX:
                    user.phone_number = user.phone_number[len(UNVERIFIED_PHONE_PREFIX):len(user.phone_number)]

                # Commit to dB
                try:
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.validate_sms(): Failed with error code '{e.args}'.")
                    return False

            else:
                app.logger.debug(f"dB.validate_sms(): Verification code doesn't match, user.email = '{user.email}'.")
                return False

    def create_new_reset_code(self, email):
        with app.app_context():
            user = db.session.query(User).filter_by(email=email).first()
            if user:
                try:
                    user.reset_code = random_code(NUM_DIGITS_CODES)
                    user.reset_code_timestamp = time.time()
                    app.logger.debug(f"dB.create_new_reset_code(): User '{email}' issued with "
                                     f"reset code '{user.reset_code}'.")
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.create_new_reset_code(): Failed with error code '{e.args}'.")
                    return False
            else:
                app.logger.error(f"dB.create_new_reset_code(): Called with invalid email = '{email}'.")
        return False

    def validate_reset_code(self, user_id, code):
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                if user.reset_code != code:
                    app.logger.debug(f"dB.validate_reset_code(): Invalid reset code for '{user.email}', "
                                     f"code was '{code}', expecting '{user.reset_code}'.")
                    return False
                else:
                    reset_timestamp = user.reset_code_timestamp
                    now = time.time()
                    age_hours = round((now - reset_timestamp) / 60 / 60, 1)
                    if now - reset_timestamp > RESET_TIMEOUT_SECS:
                        app.logger.debug(f"dB.validate_reset_code(): Valid reset code for '{user.email}', "
                                         f"but it has timed out ({age_hours} hours old).")
                        return False
                    else:
                        app.logger.debug(f"dB.validate_reset_code(): Valid reset code for '{user.email}' "
                                         f"and in date ({age_hours} hours old).")
                        return True
            else:
                app.logger.error(f"dB.validate_reset_code(): Called with invalid user_id = '{user_id}'.")
        return False

    def reset_password(self, email, password):
        with app.app_context():
            user = db.session.query(User).filter_by(email=email).first()
            if user:
                try:
                    app.logger.debug(f"dB.reset_password(): Resetting password for user '{email}'.")
                    user.reset_code = None
                    user.password = self.hash_password(password)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.reset_password(): Failed with error code '{e.args}' with email = '{email}'.")
                    return False
            else:
                app.logger.error(f"dB.reset_password(): Called with invalid email = '{email}'.")
        return False

    def delete_user(self, user_id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()

            # You can't delete Admins
            if user.admin():
                app.logger.debug(f"dB.delete_user: Rejected attempt to delete admin '{user.email}'.")
                return False

            # Extra protection in case someone finds a way around route protection
            if user.email in PROTECTED_USERS:
                app.logger.debug(f"dB.delete_user: Rejected attempt to delete protected user '{user.email}'.")
                return False

            if user:
                try:
                    # We no longer delete users, we invalidate them. This is because even though we have
                    # auto-incrementing IDs, if the last entry is deleted, the next user to register gets the next ID,
                    # which may have valid cookies stored from the previous owner!
                    user.admin_notes = f"User '{user.name}' ({user.email}) deleted " \
                                       f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                    user.password = None
                    user.email = f"{DELETED_NAME}_{user.id}"
                    user.name = DELETED_NAME
                    user.permissions = 0
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.delete_user(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.delete_user(): Called with invalid user_id = '{user_id}'.")
        return False

    def block_user(self, user_id):
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(id=user_id).first()

            # You can't block Admins
            if user.admin():
                app.logger.debug(f"dB.block_user(): Rejected attempt to block admin '{user.email}'.")
                return False

            # Extra protection in case someone finds a way around route protection
            if user.email in PROTECTED_USERS:
                app.logger.debug(f"dB.block_user(): Rejected attempt to block protected user '{user.email}'.")
                return False

            if user:
                try:
                    user.permissions = user.permissions | MASK_BLOCKED
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.block_user(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.block_user(): Called with invalid user_id = '{user_id}'.")
        return False

    def unblock_user(self, user_id):
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                try:
                    if user.permissions & MASK_BLOCKED > 0:
                        user.permissions = user.permissions - MASK_BLOCKED
                        db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.unblock_user(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.unblock_user(): Called with invalid user_id = '{user_id}'.")
        return False

    def set_readwrite(self, user_id):
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                try:
                    if user.permissions & MASK_READWRITE == 0:
                        user.permissions = user.permissions + MASK_READWRITE
                        db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.set_readwrite(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.set_readwrite(): Called with invalid user_id = '{user_id}'.")
        return False

    def set_readonly(self, user_id):
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                try:
                    if user.permissions & MASK_READWRITE > 0:
                        user.permissions = user.permissions - MASK_READWRITE
                        db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.set_readonly(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.set_readonly(): Called with invalid user_id = '{user_id}'.")
        return False

    def make_admin(self, user_id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                try:
                    if user.permissions & MASK_ADMIN == 0:
                        user.permissions = MASK_ADMIN + MASK_VERIFIED
                        db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.make_admin(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.make_admin(): Called with invalid user_id = '{user_id}'.")
        return False

    def unmake_admin(self, user_id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                if user.email in PROTECTED_USERS:
                    app.logger.debug(f"dB.unmake_admin(): Rejected attempt to unadmin protected user '{user.email}'.")
                    return False
                try:
                    if user.permissions & MASK_ADMIN == 1:
                        user.permissions = DEFAULT_PERMISSIONS_VALUE + MASK_VERIFIED
                        db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.unmake_admin(): Failed with error code '{e.args}' for user '{user.email}'.")
                    return False
            else:
                app.logger.error(f"dB.unmake_admin(): Called with invalid user_id = '{user_id}'.")
        return False

    def set_phone_number(self, user_id, phone_number):
        user = db.session.query(User).filter_by(id=user_id).first()
        if user:
            try:
                user.phone_number = phone_number
                db.session.commit()
                return True
            except Exception as e:
                app.logger.error(f"dB.set_phone_number(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                return False
        else:
            app.logger.error(f"dB.set_phone_number(): Called with invalid user_id = '{user_id}'.")
            return False

    def set_notifications(self, user_id, choices):
        user = db.session.query(User).filter_by(id=user_id).first()
        if user:
            try:
                user.notifications = choices
                db.session.commit()
                return True
            except Exception as e:
                app.logger.error(f"dB.set_notifications(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                return False
        else:
            app.logger.error(f"dB.set_notifications(): Called with invalid user_id = '{user_id}'.")
            return False

    def update_user(self, user):
        # Try and add to dB
        with app.app_context():
            try:
                db.session.add(user)
                db.session.commit()
                # Return success
                return True
            except Exception as e:
                app.logger.error(f"dB.update_user(): Failed to update user '{user.id}', error code was '{e.args}'.")
                return False

    def combo_str(self):
        return f"{self.name} ({self.id})"

    def user_from_combo_string(self, combo_string):
        # Extract id from number in last set of brackets
        # E.g. "Fred (5)"
        user_id = combo_string.split('(')[-1].split(')')[0]
        return self.find_user_from_id(user_id)

    def unsubscribe_code(self):
        # Need something secret, that no one else would know, so hash their password hash
        return hashlib.md5(f"{self.password}".encode('utf-8')).hexdigest()

    def gpx_download_code(self, gpx_id):
        # Need something secret, that no one else would know, so hash their password hash
        return hashlib.md5(f"{self.password}{gpx_id}".encode('utf-8')).hexdigest()

    # Optional: this will allow each user object to be identified by its name when printed.
    # NB Names are not unique, but emails are, hence added in brackets
    def __repr__(self):
        return f'<User {self.name} ({self.email})>'


# user = User().find_user_from_id(1)
# print(user.notification_choices_set())


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    db.create_all()


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                                Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def random_code(num_digits):
    # First digit can't be zero
    code = str(random.randint(1, 9))
    for _ in range(num_digits - 1):
        code = code + str(random.randint(0, 9))
    return int(code)


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                                Decorators
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Decorator for login required
# -------------------------------------------------------------------------------------------------------------- #

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            # Otherwise continue with the route function
            return f(*args, **kwargs)
        else:
            # Generate a custom 403 error
            return redirect(url_for('not_logged_in'))

    return decorated_function


# -------------------------------------------------------------------------------------------------------------- #
# Decorator for readwrite required
# -------------------------------------------------------------------------------------------------------------- #

def rw_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Non logged in users won't have '.readwrite()' property
        if current_user.is_authenticated:
            # Use the readwrite parameter
            if current_user.readwrite():
                # Good to go
                return f(*args, **kwargs)

        # Who are we barring access to?
        if current_user.is_authenticated:
            who = current_user.email
        else:
            who = "lot logged in"

        # Return 403
        app.logger.debug(f"rw_required(): User '{who}' attempted access to a rw only page!")
        Event().log_event("RW Access Fail", f"User '{who}' attempted access to a rw only page!")
        return redirect(url_for('not_rw'))
    return decorated_function


# -------------------------------------------------------------------------------------------------------------- #
# Decorator for admin only
# -------------------------------------------------------------------------------------------------------------- #

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Non logged in users won't have '.admin()' property
        if current_user.is_authenticated:
            # Use the admin parameter
            if current_user.admin():
                # Good to go
                return f(*args, **kwargs)

        # Who are we barring access to?
        if current_user.is_authenticated:
            who = current_user.email
        else:
            who = "lot logged in"

        # Return 403
        app.logger.debug(f"admin_only(): User '{who}' attempted access to an admin page!")
        Event().log_event("Admin Access Fail", f"User '{who}' attempted access to an admin page!")
        return abort(403)

    return decorated_function


# -------------------------------------------------------------------------------------------------------------- #
# Decorator to update last seen
# -------------------------------------------------------------------------------------------------------------- #

def update_last_seen(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Try and get IP
        try:
            if request.headers.getlist("X-Forwarded-For"):
                user_ip = request.headers.getlist("X-Forwarded-For")[0]
            else:
                user_ip = request.remote_addr
        except Exception as e:
            user_ip = "unknown"

        if not current_user.is_authenticated:
            # Not logged in, so no idea who they are
            app.logger.debug(f"update_last_seen(): User not logged in, IP = '{user_ip}', "
                             f"request = {request.method} '{request.path}'")
            return f(*args, **kwargs)
        else:
            # They are logged in, so log their activity
            app.logger.debug(f"update_last_seen(): User logged in as '{current_user.email}', IP = '{user_ip}', "
                             f"request = {request.method} '{request.path}'")
            User().log_activity(current_user.id)
            return f(*args, **kwargs)

    return decorated_function


# -------------------------------------------------------------------------------------------------------------- #
# Decorator to logout barred user
# -------------------------------------------------------------------------------------------------------------- #

def logout_barred_user(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # Not logged in, so no idea who they are
            return f(*args, **kwargs)
        else:
            user = User().find_user_from_id(current_user.id)
            if user:
                if user.blocked():
                    # Log out the user
                    app.logger.debug(f"logout_barred_user(): Logged out user '{user.email}'.")
                    Event().log_event("Blocked User logout", "Logged out user as blocked")
                    flash("You have been logged out.")
                    logout_user()
            return f(*args, **kwargs)

    return decorated_function


# -------------------------------------------------------------------------------------------------------------- #
# Decorator for readwrite
# -------------------------------------------------------------------------------------------------------------- #

def must_be_readwrite(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # Not logged in, so no idea who they are
            return abort(403)
        else:
            user = User().find_user_from_id(current_user.id)
            if user:
                if not user.blocked():
                    # Log out the user
                    app.logger.debug(f"logout_barred_user(): Logged out user '{user.email}'.")
                    Event().log_event("Blocked User logout", "Logged out user as blocked")
                    flash("You have been logged out.")
                    logout_user()
            return f(*args, **kwargs)

    return decorated_function


# -------------------------------------------------------------------------------------------------------------- #
# Export some functions to jinja that we want to use inside html templates
# -------------------------------------------------------------------------------------------------------------- #

def get_user_name(user_email):
    return User().display_name(user_email)


def get_user_id_from_email(user_email):
    return User().find_id_from_email(user_email)


# Add these to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(get_user_name=get_user_name)
app.jinja_env.globals.update(get_user_id_from_email=get_user_id_from_email)


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                                WT Forms
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Create User Registration form
# -------------------------------------------------------------------------------------------------------------- #
class CreateUserForm(FlaskForm):
    name = StringField("Name (this will appear on the website)",
                       validators=[InputRequired("Please enter your name.")])
    email = EmailField("Email address (this will be kept hidden)",
                       validators=[InputRequired("Please enter your email address."), Email()])
    password = PasswordField("Password",
                             validators=[InputRequired("Please enter a password.")])
    submit = SubmitField("Register")


# -------------------------------------------------------------------------------------------------------------- #
# Verify User email form
# -------------------------------------------------------------------------------------------------------------- #
class VerifyUserForm(FlaskForm):
    email = EmailField("Email address",
                       validators=[InputRequired("Please enter your email address."), Email()])
    verification_code = IntegerField("Verification code",
                                     validators=[InputRequired("Please enter the six digit code emailed to you.")])
    submit = SubmitField("Verify email address")


# -------------------------------------------------------------------------------------------------------------- #
# Verify User SMS form
# -------------------------------------------------------------------------------------------------------------- #
class TwoFactorLoginForm(FlaskForm):
    email = EmailField("Email address",
                       validators=[InputRequired("Please enter your email address."), Email()])
    verification_code = IntegerField("Verification code",
                                     validators=[InputRequired("Please enter the six digit code SMSed to you.")])
    submit = SubmitField("2FA Login")


# -------------------------------------------------------------------------------------------------------------- #
# Verify User SMS form
# -------------------------------------------------------------------------------------------------------------- #
class VerifySMSForm(FlaskForm):
    verification_code = IntegerField("Verification code",
                                     validators=[InputRequired("Please enter the six digit code SMSed to you.")])
    submit = SubmitField("Verify Mobile")


# -------------------------------------------------------------------------------------------------------------- #
# Login User form
# -------------------------------------------------------------------------------------------------------------- #
class LoginUserForm(FlaskForm):
    email = EmailField("Email address",
                       validators=[InputRequired("Please enter your email address."), Email()])
    # Don't require a password in the form as they might have forgotten it...
    password = PasswordField("Password")

    # Two buttons, Log in and I've forgotten my password...
    submit = SubmitField("Log in")
    forgot = SubmitField("Reset Password")
    verify = SubmitField("re-send Verification Code")


# -------------------------------------------------------------------------------------------------------------- #
# Reset Password form
# -------------------------------------------------------------------------------------------------------------- #
class ResetPasswordForm(FlaskForm):
    email = EmailField("Email address", validators=[InputRequired("Please enter your email address."), Email()])
    password1 = PasswordField("Password", validators=[InputRequired("Please enter a password.")])
    password2 = PasswordField("Password again", validators=[InputRequired("Please enter a password.")])
    submit = SubmitField("Reset password")


# -------------------------------------------------------------------------------------------------------------- #
# Custom validator for URLs (which accepts a blank field)
# -------------------------------------------------------------------------------------------------------------- #
def url_validation(form, field):
    if field.data.strip() != "" and \
         not check_url(field.data):
        raise validators.ValidationError('This is not a valid url eg https://www.strava.com/')


# -------------------------------------------------------------------------------------------------------------- #
# User details form
# -------------------------------------------------------------------------------------------------------------- #
class ChangeUserDetailsForm(FlaskForm):
    name = StringField("Change user name:", validators=[InputRequired("Please enter your name.")])
    bio = CKEditorField("Witty one liner:", validators=[])
    groups = GROUP_CHOICES.copy()
    groups.insert(0, "n/a")
    group = SelectField("Main Group:", choices=groups)
    strava = URLField("Strava url:", validators=[url_validation])
    instagram = URLField("Instagram url:", validators=[url_validation])
    twitter = URLField("Twitter / X url:", validators=[url_validation])
    facebook = URLField("Facebook url:", validators=[url_validation])
    emergency = CKEditorField("Emergency Contact Details (number, relationship, etc):", validators=[])
    submit = SubmitField("Update me!")


# -------------------------------------------------------------------------------------------------------------- #
# Clothing size form
# -------------------------------------------------------------------------------------------------------------- #
class ClothingSizesForm(FlaskForm):
    jersey_ss_relaxed = SelectField("Sunny Day (relaxed fit) SS Jersey:", choices=SIZES)
    jersey_ss_race = SelectField("Hard Day (race fit) SS Jersey:", choices=SIZES)
    jersey_ls = SelectField("Long Sleeve Jersey:", choices=SIZES)
    gilet = SelectField("Gilet:", choices=SIZES)
    bib_shorts = SelectField("Bib shorts:", choices=SIZES)
    bib_longs = SelectField("Bib longs:", choices=SIZES)
    notes = CKEditorField("Notes:", validators=[])
    submit = SubmitField("Save me!")


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    users = db.session.query(User).all()
    print(f"Found {len(users)} users in the dB")
    app.logger.debug(f"Start of day: Found {len(users)} users in the dB")


# -------------------------------------------------------------------------------------------------------------- #
# Hack to change user.start_date
# -------------------------------------------------------------------------------------------------------------- #

# with app.app_context():
#     users = User().all_users()
#     for user in users:
#         if len(user.start_date) != 8:
#             date_obj = datetime.strptime(user.start_date, "%B %d, %Y")
#             new_date = date_obj.strftime("%d%m%Y")
#             print(f"ID = {user.id}, Name = '{user.name}', Date = '{user.start_date}' or '{new_date}'")
#             user.start_date = new_date
#             db.session.add(user)
#             db.session.commit()

