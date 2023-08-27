from flask import render_template, redirect, url_for, flash, request, abort, session, make_response
from flask_login import current_user, login_required, logout_user
from werkzeug import exceptions


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, is_mobile


# -------------------------------------------------------------------------------------------------------------- #
# Import our own Classes
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, admin_only, update_last_seen, SUPER_ADMIN_USER_ID, logout_barred_user
from core.db_messages import Message, ADMIN_EMAIL
from core.dB_events import Event
from core.db_calendar import Calendar
from core.db_social import Socials


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

DEFAULT_EVENT_DAYS = 7


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Admin home page
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/admin', methods=['GET'])
@login_required
@admin_only
@update_last_seen
def admin_page():
    # ----------------------------------------------------------- #
    # Get details from the page (optional)
    # ----------------------------------------------------------- #
    event_period = request.args.get('days', None)       # Optional
    anchor = request.args.get('anchor', None)           # Optional

    # ----------------------------------------------------------- #
    # List of all events for relevant period (for admin page table)
    # ----------------------------------------------------------- #
    # Valid values for event_period are:
    #   1.  None - in which case use default value
    #   2.  An integer (number of days)
    #   3.  "all" - in which case show all events
    if not event_period:
        events = Event().all_events_days(DEFAULT_EVENT_DAYS)
        days = DEFAULT_EVENT_DAYS
    elif event_period == "all":
        events = Event().all_events()
        days = "all"
    else:
        events = Event().all_events_days(int(event_period))
        days = int(event_period)

    # ----------------------------------------------------------- #
    # List of all users (for admin page table)
    # ----------------------------------------------------------- #
    admins = User().all_admins()
    non_admins = User().all_non_admins()

    # ----------------------------------------------------------- #
    # All messages for Admin (for admin page table)
    # ----------------------------------------------------------- #
    messages = Message().all_messages_to_email(ADMIN_EMAIL)

    # ----------------------------------------------------------- #
    # All scheduled calendar events (routes)
    # ----------------------------------------------------------- #
    rides = Calendar().all_calendar()

    # ----------------------------------------------------------- #
    # All scheduled social events
    # ----------------------------------------------------------- #
    socials = Socials().all()

    # ----------------------------------------------------------- #
    # Unread messages
    # ----------------------------------------------------------- #
    count = 0
    for message in messages:
        # We add the current user's public name to each message before passing to the Jinja.
        # NB Internally we only use email as they are immutable and unique.
        message.from_name = User().find_user_from_email(message.from_email).name
        if not message.been_read():
            count += 1

    if count > 0:
        if count == 1:
            flash(f"Admin has {count} unread message")
        else:
            flash(f"Admin has {count} unread messages")

    # ----------------------------------------------------------- #
    # Serve admin page
    # ----------------------------------------------------------- #
    # If they have just changed the selection period for the event log, then we want the page to jump straight
    # to the event log itself, rather than the user scrolling down etc. We detect this is one of two ways:
    #   1.  The page was passed a value for 'event_period' because they clicked on a button in the page to
    #       change the event period view, or
    #   2.  We have been called by one of the delete event route functions and to flag to this function, that
    #       the user is looking at events, we get passed a variable 'anchor' which is set to 'eventLog'.
    # "eventLog" is the tab on the page, which a JS snippet will jump to when the page loads in the browser.

    if event_period \
            or anchor == "eventLog":
        # Jump straight to the 'eventlog'
        return render_template("admin_page.html",  year=current_year, admins=admins, non_admins=non_admins,
                               messages=messages, events=events, days=days, mobile=is_mobile(), socials=socials,
                               rides=rides, anchor="eventLog")
    elif anchor == "messages":
        # Jump straight to the 'messages'
        return render_template("admin_page.html",  year=current_year, admins=admins, non_admins=non_admins,
                               messages=messages, events=events, days=days, mobile=is_mobile(), socials=socials,
                               rides=rides, anchor="messages")
    else:
        # No jumping, just display the page from the top
        return render_template("admin_page.html", year=current_year, admins=admins, non_admins=non_admins,
                               messages=messages, events=events, days=days, mobile=is_mobile(), socials=socials,
                               rides=rides)


# -------------------------------------------------------------------------------------------------------------- #
# Make a user admin
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/make_admin', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def make_admin():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)
    try:
        password = request.form['password']
    except exceptions.BadRequestKeyError:
        password = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if password == "":
        password = " "

    # ----------------------------------------------------------- #
    # Get user's IP
    # ----------------------------------------------------------- #
    if request.headers.getlist("X-Forwarded-For"):
        user_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        user_ip = request.remote_addr

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"make_admin(): Missing user_id!.")
        Event().log_event("Make Admin Fail", f"Missing user_id")
        return abort(400)
    elif not password:
        app.logger.debug(f"make_admin(): Missing Admin's password!")
        Event().log_event("Make Admin Fail", f"Missing Admin's password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)

    # Check id is valid
    if not user:
        # Can't find that user
        app.logger.debug(f"make_admin(): FAILED to locate user user_id = '{user_id}'.")
        Event().log_event("Make Admin Fail", f"FAILED to locate user user_id = '{user_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Validate password against current_user's (admins)
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"make_admin(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        Event().log_event("Make Admin Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if current_user.id != SUPER_ADMIN_USER_ID:
        # Failed authentication
        app.logger.debug(f"make_admin(): Rejected request from '{current_user.email}' as no permissions!")
        Event().log_event(f"Make Admin Fail", f"Rejected request as no permissions. user_id = '{user_id}'")
        return abort(403)

    # ----------------------------------------------------------- #
    # Admins must have validated phone number for 2FA login
    # ----------------------------------------------------------- #
    if not user.has_valid_phone_number():
        # Can't mak admin
        flash("Sorry, user doesn't have a validated mobile number, so can't use 2FA which is mandatory for Admins!")
        app.logger.debug(f"make_admin(): Rejected request to made user_id = '{user_id}' admin as doesn't have 2FA.")
        Event().log_event(f"Make Admin Fail", f"Rejected request to made user_id = '{user_id}' "
                                              f"admin as doesn't have 2FA.")
        # Back to calling page
        return redirect(request.referrer)

    # ----------------------------------------------------------- #
    # Make admin
    # ----------------------------------------------------------- #
    if User().make_admin(user_id):
        # Success
        app.logger.debug(f"make_admin(): Success, user_id = '{user_id}'.")
        Event().log_event(f"Make Admin Success", f"User is now Admin! user_id = '{user_id}'.")
        flash(f"{user.name} is now an Admin.")
    else:
        # Should never get here!
        app.logger.debug(f"make_admin(): User().make_admin() failed, user_id = '{user_id}.")
        Event().log_event(f"Make Admin Fail", f"User().make_admin() failed, user_id = '{user_id}'.")
        flash("Sorry, something went wrong!")

    # Back to calling page
    return redirect(request.referrer)


# -------------------------------------------------------------------------------------------------------------- #
# Remove admin privileges
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/unmake_admin', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def unmake_admin():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)
    try:
        password = request.form['password']
    except exceptions.BadRequestKeyError:
        password = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if password == "":
        password = " "

    # ----------------------------------------------------------- #
    # Get user's IP
    # ----------------------------------------------------------- #
    if request.headers.getlist("X-Forwarded-For"):
        user_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        user_ip = request.remote_addr

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"unmake_admin(): Missing user_id!.")
        Event().log_event("unMake Admin Fail", f"Missing user_id")
        return abort(400)
    elif not password:
        app.logger.debug(f"unmake_admin(): Missing Admin's password!")
        Event().log_event("unMake Admin Fail", f"Missing Admin's password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)

    # Check id is valid
    if not user:
        app.logger.debug(f"unmake_admin(): FAILED to locate user user_id = '{user_id}'.")
        Event().log_event("unMake Admin Fail", f"FAILED to locate user user_id = '{user_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Validate password against current_user's (admins)
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"unmake_admin(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        Event().log_event("unMake Admin Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if current_user.id != SUPER_ADMIN_USER_ID:
        # Failed authentication
        app.logger.debug(f"unmake_admin(): Rejected request from '{current_user.email}' as no permissions!")
        Event().log_event("unMake Admin Fail", f"Rejected request as no permissions!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Make admin
    # ----------------------------------------------------------- #
    if User().unmake_admin(user_id):
        # Success
        app.logger.debug(f"unmake_admin(): Success with user_id = '{user_id}'.")
        Event().log_event("unMake Admin Success", f"User '{user.email}' is no longer an Admin!, user_id = '{user_id}'.")
        flash(f"{user.name} is no longer an Admin.")
    else:
        # Should never get here!
        app.logger.debug(f"unmake_admin(): User().unmake_admin() failed with user_id = '{user_id}'.")
        Event().log_event("unMake Admin Fail", f"User().unmake_admin() failed with user_id = '{user_id}'")
        flash("Sorry, something went wrong!")

    # Back to calling page
    return redirect(request.referrer)


# -------------------------------------------------------------------------------------------------------------- #
# Block user
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/block_user', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def block_user():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)
    try:
        password = request.form['password']
    except exceptions.BadRequestKeyError:
        password = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if password == "":
        password = " "

    # ----------------------------------------------------------- #
    # Get user's IP
    # ----------------------------------------------------------- #
    if request.headers.getlist("X-Forwarded-For"):
        user_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        user_ip = request.remote_addr

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"block_user(): Missing user_id!")
        Event().log_event("Block User Fail", f"missing user id.")
        abort(400)
    elif not password:
        app.logger.debug(f"block_user(): Missing Admin's password!")
        Event().log_event("Block User Fail", f"Missing Admin's password!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"block_user(): Invalid user user_id = '{user_id}'!")
        Event().log_event("Block User Fail", f"invalid user user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Validate password against current_user's (admins)
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"block_user(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        Event().log_event("Block User Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Block user
    # ----------------------------------------------------------- #
    if User().block_user(user_id):
        app.logger.debug(f"block_user(): User '{user_id}' is now blocked.")
        Event().log_event("Block User Success", f"User '{user_id}' is now blocked.")
        flash("User Blocked.")
    else:
        # Should never get here, but...
        app.logger.debug(f"block_user(): User().block_user() failed, user_id = '{user_id}'!")
        Event().log_event("Block User Fail", f"User().block_user() failed, user_id = '{user_id}'!")
        flash("Sorry, something went wrong...")

    # Back to user page
    return redirect(url_for('user_page', user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# unBlock user
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/unblock_user', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def unblock_user():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)
    try:
        password = request.form['password']
    except exceptions.BadRequestKeyError:
        password = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if password == "":
        password = " "

    # ----------------------------------------------------------- #
    # Get user's IP
    # ----------------------------------------------------------- #
    if request.headers.getlist("X-Forwarded-For"):
        user_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        user_ip = request.remote_addr

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"unblock_user(): Missing user_id!")
        Event().log_event("unBlock User Fail", f"missing user id.")
        abort(400)
    elif not password:
        app.logger.debug(f"unblock_user(): Missing Admin's password!")
        Event().log_event("unBlock User Fail", f"Missing Admin's password!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"unblock_user(): Invalid user user_id = '{user_id}'!")
        Event().log_event("unBlock User Fail", f"invalid user user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Validate password against current_user's (admins)
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"unblock_user(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        Event().log_event("unBlock User Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Unblock user
    # ----------------------------------------------------------- #
    if User().unblock_user(user_id):
        app.logger.debug(f"unblock_user(): User '{user_id}' is now unblocked.")
        Event().log_event("unBlock User Success", f"User '{user_id}' is now unblocked.")
        flash("User unblocked.")
    else:
        # Should never get here, but...
        app.logger.debug(f"unblock_user(): User().unblock_user() failed, user_id = '{user_id}'!")
        Event().log_event("unBlock User Fail", f"User().unblock_user() failed, user_id = '{user_id}'!")
        flash("Sorry, something went wrong...")

    # Back to user page
    return redirect(url_for('user_page', user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Delete user
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/delete_user', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def delete_user():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)
    try:
        password = request.form['password']
    except exceptions.BadRequestKeyError:
        password = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if password == "":
        password = " "

    # ----------------------------------------------------------- #
    # Get user's IP
    # ----------------------------------------------------------- #
    if request.headers.getlist("X-Forwarded-For"):
        user_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        user_ip = request.remote_addr

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"delete_user(): Missing user_id!")
        Event().log_event("Delete User Fail", f"missing user id")
        abort(400)
    elif not password:
        app.logger.debug(f"delete_user(): Missing user password!")
        Event().log_event("Delete User Fail", f"Missing user password")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"delete_user(): Invalid user user_id = '{user_id}'!")
        Event().log_event("Delete User Fail", f"Invalid user user_id = '{user_id}'!")
        abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if int(current_user.id) != int(user_id) and \
            not current_user.admin():
        app.logger.debug(f"delete_user(): User isn't allowed "
                         f"current_user.id='{current_user.id}', user_id='{user_id}'.")
        Event().log_event("Delete User Fail", f"User isn't allowed "
                                              f"current_user.id='{current_user.id}', user_id='{user_id}'.")
        abort(403)

    # ----------------------------------------------------------- #
    #  Validate user / Admin password
    # ----------------------------------------------------------- #
    if int(current_user.id) == int(user_id):
        # Validate against their own password
        if not user.validate_password(user, password, user_ip):
            app.logger.debug(f"delete_user(): Delete failed, incorrect password for user_id = '{user.id}'!")
            Event().log_event("Delete User Fail", f"Delete failed, incorrect password for user_id = '{user.id}'!")
            flash(f"Incorrect password for {user.name}.")
            return redirect(url_for('user_page', user_id=user_id))
    else:
        # Validate against current_user's (admins) password
        if not user.validate_password(current_user, password, user_ip):
            app.logger.debug(f"delete_user(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
            Event().log_event("Delete User Fail", f"Incorrect password for user_id = '{current_user.id}'!")
            flash(f"Incorrect password for {current_user.name}.")
            return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Delete the user
    # ----------------------------------------------------------- #
    if User().delete_user(user_id):
        app.logger.debug(f"delete_user(): Success, user '{user.email}' deleted.")
        Event().log_event("Delete User Success", f"User '{user.email}' deleted.")
        flash(f"User '{user.name}' successfully deleted.")

        if current_user.admin \
                and int(current_user.id) != int(user_id):
            # Admin deleting someone, so back to admin
            return redirect(url_for('admin_page'))

        # ----------------------------------------------------------- #
        # User deleting themselves, so try and clean up
        # ----------------------------------------------------------- #
        # Log them out
        logout_user()

        # Clear the session
        session.clear()

        # Delete the user's "remember me" cookie as apparently logout doesn't do that
        # From: https://stackoverflow.com/questions/25144092/flask-login-still-logged-in-after-use-logouts-when-using-remember-me
        # This seems to work now....
        response = make_response(redirect(url_for('home')))
        response.delete_cookie(app.config['REMEMBER_COOKIE_NAME'])
        return response

    else:
        # Should never get here, but...
        app.logger.debug(f"delete_user(): User().delete_user() failed for user_id = '{user_id}'.")
        Event().log_event("Delete User Fail", f"User().delete_user() failed for user_id = '{user_id}'.")
        flash("Sorry, something went wrong.")
        return redirect(url_for('user_page', user_id=user_id))


