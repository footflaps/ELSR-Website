from flask import abort, redirect, url_for, flash, session
from flask_login import UserMixin, LoginManager, current_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, SubmitField, PasswordField
from wtforms.validators import InputRequired, Email
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import time
from datetime import date, datetime
import random
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import out database connection from __init__
# -------------------------------------------------------------------------------------------------------------- #

from core import db, app, login_manager


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
#       8 :     Can Post Cafes          1 = Can add,        0 = Can't add
#       16:     Can Post GPX            1 = Can add,        0 = Can't add
#       32:     Can comment on cafes    1 = Can comment,    0 = Can't comment
#       64:     Can comment on gpx      1 = Can comment,    0 = Can't comment

# Use these masks on the Integer to extract permissions
MASK_ADMIN = 1
MASK_VERIFIED = 2
MASK_BLOCKED = 4
MASK_POST_CAFE = 8
MASK_POST_GPX = 16
MASK_COMMENT_CAFE = 32
MASK_COMMENT_GPX = 64

# Default User Permissions on verification
DEFAULT_PERMISSIONS = MASK_POST_CAFE \
                      + MASK_POST_GPX \
                      + MASK_COMMENT_CAFE \
                      + MASK_COMMENT_GPX

# One day time out
VERIFICATION_TIMEOUT_SECS = 60 * 60 * 24
RESET_TIMEOUT_SECS = 60 * 60 * 24

# Protected users (can't be deleted)
PROTECTED_USERS = os.environ['ELSR_PROTECTED_USERS']

# This is the only user who can do things like make / unmake Admins (to stop another Admin locking me out)
SUPER_ADMIN_USER_ID = 1

# Num digits for Verification / Password Reset Codes
NUM_DIGITS_CODES = 6


# -------------------------------------------------------------------------------------------------------------- #
# User loader function
# -------------------------------------------------------------------------------------------------------------- #

# You will need to provide a user_loader callback. This callback is used to reload the user object from the user
# ID stored in the session. It should take the str ID of a user, and return the corresponding user object.
# Fix for Gunicorn and multiple servers running in parallel
# See https://stackoverflow.com/questions/39684364/heroku-gunicorn-flask-login-is-not-working-properly

@login_manager.user_loader
def load_user(user_id):
    app.logger.debug(f"session = '{session}', user_id = '{user_id}'")
    # Can't say I really understand this, but Gunicorn has multiple servers running in parallel and only
    # one seemed to know the user was logged in, so you could be randomly logged out if your request was handled
    # by one of the other servers. This, seems to fix it....
    # if session:
    #     return User.query.filter_by(id=session['_user_id']).first()
    # Not sure if this ever gets executed.....
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
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)

    # Details
    name = db.Column(db.String(1000), unique=False)
    password = db.Column(db.String(100), unique=False)
    start_date = db.Column(db.String(100), unique=False)
    last_login = db.Column(db.String(100), unique=False)
    last_login_ip = db.Column(db.String(100), unique=False)

    # See above for details of how this works
    permissions = db.Column(db.Integer, unique=False)

    # In case we have to record stuff about a user
    admin_notes = db.Column(db.String(1000), unique=False)

    # For verifying email address
    verification_code = db.Column(db.Integer, unique=False)
    verification_code_timestamp = db.Column(db.Integer, unique=False)

    # For resetting password
    reset_code = db.Column(db.Integer, unique=False)
    reset_code_timestamp = db.Column(db.Integer, unique=False)

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

    def can_post_cafe(self):
        if self.permissions & MASK_POST_CAFE > 0 or \
           self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    def can_post_gpx(self):
        if self.permissions & MASK_POST_GPX > 0 or \
           self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    def can_comment_cafe(self):
        if self.permissions & MASK_COMMENT_CAFE > 0 or \
           self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    def can_comment_gpx(self):
        if self.permissions & MASK_COMMENT_GPX > 0 or \
           self.permissions & MASK_ADMIN > 0:
            return True
        else:
            return False

    def has_mail(self):
        if Message().all_unread_messages_to_email(self.email):
            return True
        else:
            return False

    # ---------------------------------------------------------------------------------------------------------- #
    # User functions
    # ---------------------------------------------------------------------------------------------------------- #

    def all_users(self):
        with app.app_context():
            users = db.session.query(User).all()
            return users

    def create_user(self, new_user, raw_password):
        # Hash password before adding to dB
        new_user.password = self.hash_password(raw_password)

        # By default new users are not admin and not verified
        new_user.verification_code = random_code(NUM_DIGITS_CODES)
        new_user.verification_code_timestamp = time.time()
        new_user.start_date = date.today().strftime("%B %d, %Y")
        new_user.permissions = 0
        print(f"User '{new_user.email}' issued with code '{new_user.verification_code}'")

        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_user)
                db.session.commit()
                # Return success
                return True
            except Exception as e:
                print(f"dB_users: Failed to create new user {new_user.email}, error code was {e.args}.")
                return False

    def send_new_verification(self, user_id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                try:
                    user.verification_code = random_code(NUM_DIGITS_CODES)
                    user.verification_code_timestamp = time.time()
                    print(f"User '{user.email}' issued with code '{user.verification_code}'")
                    # Write to dB
                    db.session.commit()
                    return True
                except Exception as e:
                    print(f"db_users: Failed to send_new_verification user.id = {user.id} error code was {e.args}.")
                    return False
        return False

    def find_user_from_id(self, id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=id).first()
            return user

    def find_user_from_email(self, email):
        with app.app_context():
            user = db.session.query(User).filter_by(email=email).first()
            return user

    def display_name(self, email):
        with app.app_context():
            user = self.find_user_from_email(email)
            if user:
                return user.name
            else:
                return "unknown"

    def name_from_id(self, id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=id).first()
            return user.name

    def hash_password(self, raw_password):
        return generate_password_hash(raw_password, method='pbkdf2:sha256', salt_length=8)

    def validate_password(self, user, raw_password, user_ip):
        with app.app_context():
            if check_password_hash(user.password, raw_password):
                try:
                    # Update last login details
                    user = db.session.query(User).filter_by(id=user.id).first()
                    user.last_login = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    user.last_login_ip = user_ip
                    db.session.commit()
                    return True
                except Exception as e:
                    print(f"db_users: Failed to validate password user.id = {user.id} error code was {e.args}.")
                    return False

            else:
                return False

    def log_activity(self, user_id):
        with app.app_context():
            try:
                user = db.session.query(User).filter_by(id=user_id).first()
                user.last_login = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                db.session.commit()
                return True
            except Exception as e:
                print(f"db_users: Failed to update activity user_id = {user_id} error code was {e.args}.")
                return False

    def validate_email(self, user, code):
        with app.app_context():

            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(id=user.id).first()
            now = time.time()

            # Debug
            print(f"dB_users: Verifying user.id = {user.id}, user.email = {user.email}")
            print(f"dB_users: Received code = {code}, user.verification_code = {user.verification_code}")
            print(f"dB_users: user.verification_code_timestamp = {user.verification_code_timestamp}, now = {now}")

            # Has the code timed out
            if now - user.verification_code_timestamp > VERIFICATION_TIMEOUT_SECS:
                # Code has time out
                print("dB_users: Verification code has timed out.")
                return False

            if int(code) == int(user.verification_code):
                print(f"dB_users: Verification code matches, before user.permissions = {user.permissions}")
                user.permissions = user.permissions \
                                   | MASK_VERIFIED \
                                   | DEFAULT_PERMISSIONS
                print(f"dB_users: Verification code matches, after user.permissions = {user.permissions}")

                # Clear verification data, so it can't be used again
                user.verification_code = int(0)
                user.verification_code_timestamp = 0

                # Commit to dB
                try:
                    db.session.commit()
                    return True
                except Exception as e:
                    print(f"db_users: Failed to validate email user.id = {user.id} error code was {e.args}.")
                    return False

            else:
                print("dB_users: Verification code doesn't match.")
                return False

    def send_reset(self, email):
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(email=email).first()
            if user:
                try:
                    print(user.id, user.email)
                    user.reset_code = random_code(NUM_DIGITS_CODES)
                    user.reset_code_timestamp = time.time()
                    print(f"User '{email}' issued with reset code '{user.reset_code}'")
                    db.session.commit()
                    return True
                except Exception as e:
                    print(f"db_users: Failed to send reset user.id = {user.id} error code was {e.args}.")
                    return False
        return False

    def validate_reset_code(self, user_id, code):
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                if user.reset_code != code:
                    print(f"dB_users: Invalid reset code for '{user.email}', code was '{code}', expecting '{user.reset_code}'.")
                    return False
                else:
                    reset_timestamp = user.reset_code_timestamp
                    now = time.time()
                    age_hours = round((now - reset_timestamp) / 60 / 60, 1)
                    if now - reset_timestamp > RESET_TIMEOUT_SECS:
                        print(f"dB_users: Valid reset code for '{user.email}', but it has timed out ({age_hours} hours old)")
                        return False
                    else:
                        print(f"dB_users: Valid reset code for '{user.email}' and in date ({age_hours} hours old).")
                        return True

        return False

    def reset_codes(self):
        codes = {}
        with app.app_context():
            users = db.session.query(User).filter(User.reset_code != "").all()
            for user in users:
                print(user.email, user.reset_code)
                codes[str(user.reset_code)] = user.email
            return codes

    def reset_password(self, email, password):
        with app.app_context():
            user = db.session.query(User).filter_by(email=email).first()
            if user:
                try:
                    print(f"dB_users: Resetting password for user '{email}'")
                    user.reset_code = None
                    user.password = self.hash_password(password)
                    db.session.commit()
                    return True
                except Exception as e:
                    print(f"db_users: Failed to reset password user.id = {user.id} error code was {e.args}.")
                    return False
        return False

    def delete_user(self, user_id):
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()

            # You can't delete Admins
            if user.admin():
                print(f"dB_users: Rejected attempt to delete admin '{user.email}'.")
                return False

            # Extra protection in case someone finds a way around route protection
            if user.email in PROTECTED_USERS:
                print(f"dB_users: Rejected attempt to delete protected user '{user.email}'.")
                return False

            if user:
                try:
                    # Delete the user
                    print(f"dB_users: Deleting user '{user.email}'.")
                    db.session.delete(user)
                    db.session.commit()
                    return True
                except Exception as e:
                    print(f"db_users: Failed to delete user.id = {user.id} error code was {e.args}.")
                    return False
        return False

    def block_user(self, user_id):
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(id=user_id).first()

            # You can't block Admins
            if user.admin():
                print(f"dB_users: Rejected attempt to block admin '{user.email}'.")
                return False

            # Extra protection in case someone finds a way around route protection
            if user.email in PROTECTED_USERS:
                print(f"dB_users: Rejected attempt to block protected user '{user.email}'.")
                return False

            if user:
                try:
                    user.permissions = user.permissions | MASK_BLOCKED
                    db.session.commit()
                    return True
                except Exception as e:
                    print(f"db_users: Failed to block user.id = {user.id} error code was {e.args}.")
                    return False
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
                    print(f"db_users: Failed to unblock user.id = {user.id} error code was {e.args}.")
                    return False
        return False

    def make_admin(self, user_id):
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                try:
                    if user.permissions & MASK_ADMIN == 0:
                        user.permissions = user.permissions | MASK_ADMIN
                        db.session.commit()
                    return True
                except Exception as e:
                    print(f"db_users: Failed to make admin user.id = {user.id} error code was {e.args}.")
                    return False
        return False

    def unmake_admin(self, user_id):
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(User).filter_by(id=user_id).first()
            if user:
                if user.email in PROTECTED_USERS:
                    print(f"dB_users: Rejected attempt to unadmin protected user")
                    return False
                try:
                    if user.permissions & MASK_ADMIN == 1:
                        user.permissions = user.permissions - MASK_ADMIN
                        db.session.commit()
                    return True
                except Exception as e:
                    print(f"db_users: Failed to unmake admin user.id = {user.id} error code was {e.args}.")
                    return False
        return False


    # Optional: this will allow each user object to be identified by its name when printed.
    # NB Names are not unique, but emails are, hence added in brackets
    def __repr__(self):
        return f'<User {self.name} ({self.email})>'


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

# This one doesn't seem to work, need to use the one in the same module as the Primary dB
with app.app_context():
    db.create_all()


# Seems we can do this as well!
# print(User.query.all())
# print(User.query.filter_by(id=1).first())


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
# Create a decorator for admin only
# -------------------------------------------------------------------------------------------------------------- #

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Use the admin parameter
        if current_user.admin():
            # Otherwise continue with the route function
            return f(*args, **kwargs)
        else:
            if current_user.is_authenticated:
                who = current_user.email
            else:
                who = "lot logged in"
            Event().log_event("Admin Access Fail", f"User '{who}' attempted access to an admin page!")
            print(f"User '{who}' attempted access to an admin page!")
            return abort(403)

    return decorated_function


def update_last_seen(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # Not logged in, so no idea who they are
            app.logger.debug(f"User not logged in.")
            return f(*args, **kwargs)
        else:
            # They are logged in, so log their activity
            app.logger.debug(f"User logged in '{current_user.email}'.")
            User().log_activity(current_user.id)

            return f(*args, **kwargs)

    return decorated_function


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
                    flash("You have been logged out.")
                    print(f"Logged out user '{user.email}' as barred.")
                    Event().log_event("Blocked User logout", "Logged out user as blocked")
                    logout_user()
            return f(*args, **kwargs)

    return decorated_function


# -------------------------------------------------------------------------------------------------------------- #
# Export some functions to jinja that we want to use inside html templates
# -------------------------------------------------------------------------------------------------------------- #

def get_user_name(user_email):
    return User().display_name(user_email)


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(get_user_name=get_user_name)


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
    name = StringField("Name (this will appear on the website)", validators=[InputRequired("Please enter your name.")])
    email = EmailField("Email address (this will be kept hidden)", validators=[InputRequired("Please enter your email address."), Email()])
    password = PasswordField("Password", validators=[InputRequired("Please enter a password.")])
    submit = SubmitField("Register")


# -------------------------------------------------------------------------------------------------------------- #
# Verify User form
# -------------------------------------------------------------------------------------------------------------- #
class VerifyUserForm(FlaskForm):
    email = EmailField("Email address", validators=[InputRequired("Please enter your email address."), Email()])
    verification_code = PasswordField("Verification code",
                                      validators=[InputRequired("Please enter the six digit code emailed to you.")])
    submit = SubmitField("Verify email address")


# -------------------------------------------------------------------------------------------------------------- #
# Login User form
# -------------------------------------------------------------------------------------------------------------- #
class LoginUserForm(FlaskForm):
    email = EmailField("Email address", validators=[InputRequired("Please enter your email address."), Email()])
    # Don't require a password in the form as they might have forgotten it...
    password = PasswordField("Password")

    # Two buttons, Log in and I've forgotten my password...
    submit = SubmitField("Log in")
    forgot = SubmitField("Forgotten Password")
    verify = SubmitField("Send Verification Code")


# -------------------------------------------------------------------------------------------------------------- #
# Reset Password form
# -------------------------------------------------------------------------------------------------------------- #
class ResetPasswordForm(FlaskForm):
    email = EmailField("Email address", validators=[InputRequired("Please enter your email address."), Email()])
    password1 = PasswordField("Password", validators=[InputRequired("Please enter a password.")])
    password2 = PasswordField("Password again", validators=[InputRequired("Please enter a password.")])
    submit = SubmitField("Reset password")


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    users = db.session.query(User).all()
    print(f"Found {len(users)} users in the dB")