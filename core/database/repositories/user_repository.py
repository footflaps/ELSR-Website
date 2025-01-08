from werkzeug.security import generate_password_hash, check_password_hash
import time
from datetime import date, datetime
import random
from sqlalchemy import func


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import db, app, login_manager, PROTECTED_USERS
from core.database.models.user_model import (UserModel, MASK_ADMIN, MASK_VERIFIED, MASK_BLOCKED, MASK_READWRITE, 
                                             UNVERIFIED_PHONE_PREFIX, NOTIFICATIONS_DEFAULT_VALUE, NOTIFICATIONS)


# Default User Permissions on verification
DEFAULT_PERMISSIONS_VALUE = 0

# One day time out for email
VERIFICATION_TIMEOUT_SECS = 60 * 60 * 24
RESET_TIMEOUT_SECS = 60 * 60 * 24

# 15 min time out for SMS
SMS_VERIFICATION_TIMEOUT_SECS = 60 * 15

# This is the only user who can do things like make / unmake Admins (to stop another Admin locking me out)
SUPER_ADMIN_USER_ID = 1

# Num digits for Verification / Password Reset Codes
NUM_DIGITS_CODES = 6

# For soft deleting users, we change their name to
DELETED_NAME = "DELETED"

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
def load_user(user_id: int) -> UserModel | None:
    # Only log user details on the webserver
    # if os.path.exists("/home/ben_freeman_eu/elsr_website/ELSR-Website/env_vars.py"):
    #     app.logger.debug(f"session = '{session}', user_id = '{user_id}'")
    return UserRepository.query.get(int(user_id))


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define User Repository Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class UserRepository(UserModel):

    # ---------------------------------------------------------------------------------------------------------- #
    # Create
    # ---------------------------------------------------------------------------------------------------------- #
    def create_user(self, new_user: UserModel, raw_password: str) -> bool:
        # Hash password before adding to dB
        new_user.password = self.hash_password(raw_password)

        # By default, new users are not verified and have no permissions until verified
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
                return True
            
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"dB.create_user(): Failed with error code '{e.args}'.")
                return False

    # ---------------------------------------------------------------------------------------------------------- #
    # Update
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def update_user(user: UserModel) -> bool:
        # Try and add to dB
        with app.app_context():
            try:
                db.session.add(user)
                db.session.commit()
                return True
            
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"dB.update_user(): Failed to update user '{user.id}', error code was '{e.args}'.")
                return False

    @staticmethod
    def block_user(user_id: int) -> bool:
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(UserModel).filter_by(id=user_id).first()

            if user:
                # You can't block Admins
                if user.admin:
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
                        db.session.rollback()
                        app.logger.error(f"dB.block_user(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                        return False
                else:
                    app.logger.error(f"dB.block_user(): Called with invalid user_id = '{user_id}'.")
            else:
                app.logger.error(f"dB.block_user(): Called with invalid user_id = '{user_id}'.")

        return False

    @staticmethod
    def unblock_user(user_id: int) -> bool:
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(UserModel).filter_by(id=user_id).first()
            if user:
                try:
                    if user.permissions & MASK_BLOCKED > 0:
                        user.permissions = user.permissions - MASK_BLOCKED
                        db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"dB.unblock_user(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False

            else:
                app.logger.error(f"dB.unblock_user(): Called with invalid user_id = '{user_id}'.")

        return False

    @staticmethod
    def create_new_verification(user_id: int) -> bool:
        with app.app_context():
            user = db.session.query(UserModel).filter_by(id=user_id).first()
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
                    db.session.rollback()
                    app.logger.error(f"dB.create_new_verification(): Failed with error code '{e.args}' "
                                     f"for user_id = '{user_id}'.")
                    return False

            else:
                app.logger.error(f"dB.create_new_verification(): Called with invalid user_id = '{user_id}'.")

        return False

    @staticmethod
    def generate_sms_code(user_id: int) -> bool:
        with app.app_context():
            user = db.session.query(UserModel).filter_by(id=user_id).first()
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
                    db.session.rollback()
                    app.logger.error(f"dB.generate_sms_code(): Failed with error code '{e.args}' "
                                     f"for user_id = '{user_id}'.")
                    return False

            else:
                app.logger.error(f"dB.generate_sms_code(): Called with invalid user_id = '{user_id}'.")

        return False

    @staticmethod
    def validate_password(user: UserModel, raw_password: str, user_ip: str) -> bool:
        with app.app_context():
            if user.password:
                if check_password_hash(user.password, raw_password):
                    try:
                        # Update last login details
                        user = db.session.query(UserModel).filter_by(id=user.id).first()
                        user.last_login = str(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
                        user.last_login_ip = str(user_ip)
                        db.session.commit()
                        return True

                    except Exception as e:
                        db.session.rollback()
                        app.logger.error(f"dB.validate_password(): Failed with error code '{e.args}'.")
                        return False

            else:
                app.logger.error(f"dB.validate_password(): Called for user without password, user.id = '{user.id}'.")
                return False

        return False

    @staticmethod
    def log_activity(user_id: str) -> bool:
        with app.app_context():
            try:
                user: UserModel | None = db.session.query(UserModel).filter_by(id=user_id).first()
                if user:
                    user.last_login = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    db.session.commit()
                    return True
                else:
                    app.logger.error(f"dB.log_activity(): Called with invalid user_id = '{user_id}'.")
                    return False

            except Exception as e:
                db.session.rollback()
                app.logger.error(f"dB.log_activity(): Failed with error code '{e.args}'.")
                return False

    @staticmethod
    # ToDo: Fix this to not re-acquire
    def validate_email(user: UserModel, code: str) -> bool:
        with app.app_context():

            # For some reason we need to re-acquire the user within this context
            user = db.session.query(UserModel).filter_by(id=user.id).first()
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
                    db.session.rollback()
                    app.logger.error(f"dB.validate_email(): Failed with error code '{e.args}'.")
                    return False

            else:
                app.logger.debug(f"dB.validate_email(): Verification code doesn't match, user.email = '{user.email}'.")
                return False

    @staticmethod
    def validate_sms(user: UserModel, code: str) -> bool:
        with app.app_context():

            # For some reason we need to re-acquire the user within this context
            user = db.session.query(UserModel).filter_by(id=user.id).first()
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
                    db.session.rollback()
                    app.logger.error(f"dB.validate_sms(): Failed with error code '{e.args}'.")
                    return False

            else:
                app.logger.debug(f"dB.validate_sms(): Verification code doesn't match, user.email = '{user.email}'.")
                return False

    @staticmethod
    def create_new_reset_code(email: str) -> bool:
        with app.app_context():
            user = db.session.query(UserModel).filter_by(email=email).first()
            if user:
                try:
                    user.reset_code = random_code(NUM_DIGITS_CODES)
                    user.reset_code_timestamp = int(time.time())
                    app.logger.debug(f"dB.create_new_reset_code(): User '{email}' issued with "
                                     f"reset code '{user.reset_code}'.")
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"dB.create_new_reset_code(): Failed with error code '{e.args}'.")
                    return False
            else:
                app.logger.error(f"dB.create_new_reset_code(): Called with invalid email = '{email}'.")

        return False

    def reset_password(self, email: str, password: str) -> bool:
        with app.app_context():
            user = db.session.query(UserModel).filter_by(email=email).first()
            if user:
                try:
                    app.logger.debug(f"dB.reset_password(): Resetting password for user '{email}'.")
                    user.reset_code = None
                    user.password = self.hash_password(password)
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"dB.reset_password(): Failed with error code '{e.args}' with email = '{email}'.")
                    return False

            else:
                app.logger.error(f"dB.reset_password(): Called with invalid email = '{email}'.")

        return False

    @staticmethod
    def set_readwrite(user_id: int) -> bool:
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(UserModel).filter_by(id=user_id).first()
            if user:
                try:
                    if user.permissions & MASK_READWRITE == 0:
                        user.permissions = user.permissions + MASK_READWRITE
                        db.session.commit()
                    return True
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"dB.set_readwrite(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.set_readwrite(): Called with invalid user_id = '{user_id}'.")
        return False

    @staticmethod
    def set_readonly(user_id: int) -> bool:
        with app.app_context():
            # For some reason we need to re-acquire the user within this context
            user = db.session.query(UserModel).filter_by(id=user_id).first()
            if user:
                try:
                    if user.permissions & MASK_READWRITE > 0:
                        user.permissions = user.permissions - MASK_READWRITE
                        db.session.commit()
                    return True
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"dB.set_readonly(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.set_readonly(): Called with invalid user_id = '{user_id}'.")
        return False

    @staticmethod
    def make_admin(user_id: int) -> bool:
        with app.app_context():
            user = db.session.query(UserModel).filter_by(id=user_id).first()
            if user:
                try:
                    if user.permissions & MASK_ADMIN == 0:
                        user.permissions = MASK_ADMIN + MASK_VERIFIED
                        db.session.commit()
                    return True
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"dB.make_admin(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False
            else:
                app.logger.error(f"dB.make_admin(): Called with invalid user_id = '{user_id}'.")
        return False

    @staticmethod
    def unmake_admin(user_id: int) -> bool:
        with app.app_context():
            user = db.session.query(UserModel).filter_by(id=user_id).first()
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
                    db.session.rollback()
                    app.logger.error(f"dB.unmake_admin(): Failed with error code '{e.args}' for user '{user.email}'.")
                    return False
            else:
                app.logger.error(f"dB.unmake_admin(): Called with invalid user_id = '{user_id}'.")
        return False

    @staticmethod
    def set_phone_number(user_id: int, phone_number: str) -> bool:
        user = db.session.query(UserModel).filter_by(id=user_id).first()
        if user:
            try:
                user.phone_number = phone_number
                db.session.commit()
                return True
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"dB.set_phone_number(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                return False
        else:
            app.logger.error(f"dB.set_phone_number(): Called with invalid user_id = '{user_id}'.")
            return False

    @staticmethod
    def set_notifications(user_id: int, choices: int) -> bool:
        user = db.session.query(UserModel).filter_by(id=user_id).first()
        if user:
            try:
                user.notifications = choices
                db.session.commit()
                return True
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"dB.set_notifications(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                return False
        else:
            app.logger.error(f"dB.set_notifications(): Called with invalid user_id = '{user_id}'.")
            return False

    # ---------------------------------------------------------------------------------------------------------- #
    # Delete
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def delete_user(user_id: int) -> bool:
        with app.app_context():
            user: UserModel | None = db.session.query(UserModel).filter_by(id=user_id).first()

            if user:
                # You can't delete Admins
                if user.admin:
                    app.logger.debug(f"dB.delete_user: Rejected attempt to delete admin '{user.email}'.")
                    return False

                # Extra protection in case someone finds a way around route protection
                if user.email in PROTECTED_USERS:
                    app.logger.debug(f"dB.delete_user: Rejected attempt to delete protected user '{user.email}'.")
                    return False

                try:
                    # We no longer delete users, we invalidate them. This is because even though we have
                    # auto-incrementing IDs, if the last entry is deleted, the next user to register gets the next ID,
                    # which may have valid cookies stored from the previous owner!
                    user.admin_notes = f"User '{user.name}' ({user.email}) deleted " \
                                       f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                    user.password = ""
                    user.email = f"{DELETED_NAME}_{user.id}"
                    user.name = DELETED_NAME
                    user.permissions = 0
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"dB.delete_user(): Failed with error code '{e.args}' for user_id = '{user_id}'.")
                    return False

            else:
                app.logger.error(f"dB.delete_user(): Called with invalid user_id = '{user_id}'.")
        
        return False

    # ---------------------------------------------------------------------------------------------------------- #
    # Search
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def all_users() -> list[UserModel]:
        with app.app_context():
            users = db.session.query(UserModel).filter(UserModel.name != DELETED_NAME).all()
            return users

    @staticmethod
    def all_users_sorted() -> list[UserModel]:
        with app.app_context():
            users = db.session.query(UserModel).order_by(func.lower(UserModel.name)).filter(UserModel.name != DELETED_NAME).all()
            return users

    @staticmethod
    def all_admins() -> list[UserModel]:
        with app.app_context():
            admins = db.session.query(UserModel).filter(UserModel.permissions == MASK_ADMIN + MASK_VERIFIED).all()
            return admins

    @staticmethod
    def all_non_admins() -> list[UserModel]:
        with (app.app_context()):
            non_admins = db.session.query(UserModel).filter(UserModel.permissions != MASK_ADMIN + MASK_VERIFIED) \
                                                    .filter(UserModel.name != DELETED_NAME) \
                                                    .all()
            return non_admins

    @staticmethod
    def one_by_id(user_id: int) -> UserModel | None:
        with app.app_context():
            user = db.session.query(UserModel).filter_by(id=user_id).first()
            return user

    @staticmethod
    def one_by_email(email: str) -> UserModel | None:
        with app.app_context():
            user = db.session.query(UserModel).filter_by(email=email).first()
            return user

    @staticmethod
    def find_id_from_email(email: str) -> int | None:
        with app.app_context():
            user = db.session.query(UserModel).filter_by(email=email).first()
            if user:
                return user.id
            else:
                return None

    @classmethod
    def user_from_combo_string(cls, combo_string: str) -> UserModel | None:
        # Extract id from number in last set of brackets
        # E.g. "Fred (5)"
        try:
            user_id = int(combo_string.split('(')[-1].split(')')[0])
        except Exception:
            return None
        return cls.one_by_id(user_id)

    # ---------------------------------------------------------------------------------------------------------- #
    # Other
    # ---------------------------------------------------------------------------------------------------------- #

    @staticmethod
    def notification_choice(user: UserModel, notification_type: str) -> bool:
        """
        Look up whether a given user has selected to receive email notifications for a
        given notification type.
        :param user:                            User ORM
        :param notification_type:               The name of the notification type
        :return:                                True if they have, False otherwise
        """
        # Handle unset as new column
        if not user.notifications:
            user.notifications = 0
        # Loop through our set
        for notification in NOTIFICATIONS:
            name: str = notification['name']
            bit_mask: int = notification['mask']
            if name == notification_type:
                return bool(user.notifications & bit_mask)
        return False

    def check_name_in_use(self, name: str) -> bool:
        users = self.all_users()
        for user in users:
            if name.strip().lower() == user.name.strip().lower():
                return True
        return False

    @staticmethod
    def hash_password(raw_password: str) -> str:
        return generate_password_hash(raw_password, method='pbkdf2:sha256', salt_length=8)

    @staticmethod
    def validate_reset_code(user_id: int, code: str) -> bool:
        with app.app_context():
            user = db.session.query(UserModel).filter_by(id=user_id).first()
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


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                                Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def random_code(num_digits: int) -> int:
    """
    Create a random authentication code which comprises num_digits digits.
    NB The code will always have 1 to 9 as the first digit, never zero.
    :param num_digits:              Number of digits in the code
    :return:                        An integer
    """
    # First digit can't be zero
    code: str = str(random.randint(1, 9))
    for _ in range(num_digits - 1):
        code = code + str(random.randint(0, 9))
    return int(code)
