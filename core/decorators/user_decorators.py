from flask import abort, flash, request, redirect, url_for
from flask_login import current_user, logout_user
from functools import wraps


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import app
from core.database.repositories.db_users import User
from core.database.repositories.event_repository import EventRepository


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
        # Non-logged-in users won't have '.readwrite()' property
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
        EventRepository().log_event("RW Access Fail", f"User '{who}' attempted access to a rw only page!")
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
        EventRepository().log_event("Admin Access Fail", f"User '{who}' attempted access to an admin page!")
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
                    EventRepository().log_event("Blocked User logout", "Logged out user as blocked")
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
                    EventRepository().log_event("Blocked User logout", "Logged out user as blocked")
                    flash("You have been logged out.")
                    logout_user()
            return f(*args, **kwargs)

    return decorated_function




