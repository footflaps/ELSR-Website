from flask import render_template, redirect, url_for, flash, request, abort, session, make_response
from flask_login import current_user, login_required, logout_user
from werkzeug import exceptions
from threading import Thread


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
from core.subs_email_sms import send_sms, get_twilio_balance
from core.subs_google_maps import maps_enabled, set_enable_maps, set_disable_maps


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
# Admin home page - Admin only
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
    # Double check for Admin only (in case decorator fails)
    # ----------------------------------------------------------- #
    if not current_user.admin():
        app.logger.debug(f"admin_page(): Non Admin access, user_id = '{current_user.id}'!")
        Event().log_event("Admin Page Fail", f"on Admin access, user_id = '{current_user.id}'!")
        return abort(403)

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
    # Twilio balance
    # ----------------------------------------------------------- #
    twilio_balance = get_twilio_balance()

    # ----------------------------------------------------------- #
    # Google Maps Status
    # ----------------------------------------------------------- #

    map_status = maps_enabled()

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
                               rides=rides, twilio_balance=twilio_balance, map_status=map_status, anchor="eventLog")
    elif anchor == "messages":
        # Jump straight to the 'messages'
        return render_template("admin_page.html",  year=current_year, admins=admins, non_admins=non_admins,
                               messages=messages, events=events, days=days, mobile=is_mobile(), socials=socials,
                               rides=rides, twilio_balance=twilio_balance, map_status=map_status, anchor="messages")
    else:
        # No jumping, just display the page from the top
        return render_template("admin_page.html", year=current_year, admins=admins, non_admins=non_admins,
                               messages=messages, events=events, days=days, mobile=is_mobile(), socials=socials,
                               rides=rides, twilio_balance=twilio_balance, map_status=map_status)


# -------------------------------------------------------------------------------------------------------------- #
# Make a user admin - Admin only
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
    # Restrict access - only Super Admin can do this
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
# Remove admin privileges - Admin only
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
    # Restrict access - only Super Admin can do this
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
# Block user - Admin only
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
        app.logger.debug(f"block_user(): Block failed, incorrect password for user_id = '{current_user.id}'!")
        Event().log_event("Block User Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Can't block yourself nor an admin
    # ----------------------------------------------------------- #
    if current_user.id == user.id:
        app.logger.debug(f"block_user(): Block failed, admin can't block themselves, user_id = '{current_user.id}'.")
        Event().log_event("Block User Fail", f"Admin can't block themselves, user_id = '{current_user.id}'.")
        flash(f"You can't block yourself!")
        return redirect(url_for('user_page', user_id=user_id))
    if user.admin():
        app.logger.debug(f"block_user(): Block failed, can't block Admin, user_id = '{current_user.id}'.")
        Event().log_event("Block User Fail", f"Can't block Admin, user_id = '{current_user.id}'.")
        flash(f"You can't block an Admin!")
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
# unBlock user - Admin only
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
    # Can't block yourself nor an admin
    # ----------------------------------------------------------- #
    if current_user.id == user.id:
        app.logger.debug(
            f"block_user(): ubBlock failed, admin can't unblock themselves, user_id = '{current_user.id}'.")
        Event().log_event("unBlock User Fail", f"Admin can't unblock themselves, user_id = '{current_user.id}'.")
        flash(f"You can't unblock yourself!")
        return redirect(url_for('user_page', user_id=user_id))
    if user.admin():
        app.logger.debug(f"unblock_user(): unBlock failed, can't block Admin, user_id = '{current_user.id}'.")
        Event().log_event("unBlock User Fail", f"Can't unblock Admin, user_id = '{current_user.id}'.")
        flash(f"You can't unblock an Admin!")
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
# Give user write permissions - Admin only
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/user_readwrite', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def user_readwrite():
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
        app.logger.debug(f"user_readwrite(): Missing user_id!")
        Event().log_event("ReadWrite Fail", f"Missing user id")
        abort(400)
    elif not password:
        app.logger.debug(f"user_readwrite(): Missing user password!")
        Event().log_event("ReadWrite Fail", f"Missing user password")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"user_readwrite(): Invalid user user_id = '{user_id}'!")
        Event().log_event("ReadWrite Fail", f"Invalid user user_id = '{user_id}'!")
        abort(404)

    # ----------------------------------------------------------- #
    # Can't edit yourself nor an admin
    # ----------------------------------------------------------- #
    if current_user.id == user.id:
        app.logger.debug(f"user_readwrite(): ubBlock failed, admin can't unblock themselves, user_id = '{user_id}'.")
        Event().log_event("ReadWrite Fail", f"Admin can't unblock themselves, user_id = '{user_id}'.")
        flash(f"You can't unblock yourself!")
        return redirect(url_for('user_page', user_id=user_id))
    if user.admin():
        app.logger.debug(f"user_readwrite(): unBlock failed, can't block Admin, user_id = '{user_id}'.")
        Event().log_event("ReadWrite Fail", f"Can't unblock Admin, user_id = '{user_id}'.")
        flash(f"You can't unblock an Admin!")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    #  Validate against current_user's (admins) password
    # ----------------------------------------------------------- #
    if not user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"user_readwrite(): Incorrect password for user_id = '{current_user.id}'!")
        Event().log_event("ReadWrite Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for '{current_user.name}'.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Set Read Write permission
    # ----------------------------------------------------------- #
    if User().set_readwrite(user_id):
        app.logger.debug(f"user_readwrite(): Success, user can now write, user.email = '{user.email}'.")
        Event().log_event("ReadWrite Success", f"User can now write, user.email = '{user.email}'.")
        flash(f"User '{user.name}' now has Write permissions.")
        Message().send_readwrite_message(user.email)
        return redirect(url_for('user_page', user_id=user_id))
    else:
        # Should never get here, but...
        app.logger.debug(f"user_readwrite(): User().set_readwrite() failed for user.email = '{user.email}'.")
        Event().log_event("ReadWrite Fail", f"User().set_readwrite() failed for user.email = '{user.email}'.")
        flash("Sorry, something went wrong.")
        return redirect(url_for('user_page', user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Give user read only permissions - Admin only
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/user_readonly', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def user_readonly():
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
        app.logger.debug(f"user_readonly(): Missing user_id!")
        Event().log_event("ReadOnly Fail", f"Missing user id")
        abort(400)
    elif not password:
        app.logger.debug(f"user_readonly(): Missing user password!")
        Event().log_event("ReadOnly Fail", f"Missing user password")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"user_readonly(): Invalid user user_id = '{user_id}'!")
        Event().log_event("ReadOnly Fail", f"Invalid user user_id = '{user_id}'!")
        abort(404)

    # ----------------------------------------------------------- #
    # Can't edit yourself nor an admin
    # ----------------------------------------------------------- #
    if current_user.id == user.id:
        app.logger.debug(f"user_readonly(): ubBlock failed, admin can't unblock themselves, '{current_user.email}'.")
        Event().log_event("ReadOnly Fail", f"Admin can't unblock themselves, '{current_user.email}'.")
        flash(f"You can't unblock yourself!")
        return redirect(url_for('user_page', user_id=user_id))
    if user.admin():
        app.logger.debug(f"user_readonly(): unBlock failed, can't block Admin, "
                         f"'{current_user.email}' blocking '{user.email}'.")
        Event().log_event("ReadOnly Fail", f"Can't unblock Admin, '{current_user.email}' blocking '{user.email}'.")
        flash(f"You can't unblock an Admin!")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    #  Validate against current_user's (admins) password
    # ----------------------------------------------------------- #
    if not user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"user_readonly(): Incorrect password for '{current_user.email}'!")
        Event().log_event("ReadOnly Fail", f"Incorrect password for '{current_user.email}'!")
        flash(f"Incorrect password for '{current_user.name}'.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Set Read Only permission
    # ----------------------------------------------------------- #
    if User().set_readonly(user_id):
        app.logger.debug(f"user_readonly(): Success, user is Readonly, user.email = '{user.email}'.")
        Event().log_event("ReadOnly Success", f"User is Readonly, user.email = '{user.email}'.")
        flash(f"User '{user.name}' is now Read ONLY.")
        Message().send_readonly_message(user.email)
        return redirect(url_for('user_page', user_id=user_id))
    else:
        # Should never get here, but...
        app.logger.debug(f"user_readonly(): User().set_readonly() failed for user.email = '{user.email}'.")
        Event().log_event("ReadOnly Fail", f"User().set_readonly() failed for user.email = '{user.email}'.")
        flash("Sorry, something went wrong.")
        return redirect(url_for('user_page', user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Send a new verification code
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/send_verification', methods=['GET'])
@login_required
@admin_only
@update_last_seen
def reverify_user():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"reverify_user(): Missing user_id!")
        Event().log_event("Send Verify Fail", f"Missing user_id.")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"reverify_user(): Invalid user user_id = '{user_id}'!")
        Event().log_event("Send Verify Fail", f"Invalid user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Send verification code
    # ----------------------------------------------------------- #
    if User().create_new_verification(user_id):
        app.logger.debug(f"reverify_user(): Verification code sent user_id = '{user_id}'.")
        Event().log_event("Send Verify Pass", f"Verification code sent user_id = '{user_id}'.")
        flash("Verification code sent!")
    else:
        # Should never get here, but...
        app.logger.debug(f"reverify_user(): User().create_new_verification() failed, user_id = '{user_id}'!")
        Event().log_event("Send Verify Fail", f"User().create_new_verification() failed, user_id = '{user_id}'!")
        flash("Sorry, something went wrong!")

    # Back to user page
    return redirect(url_for('user_page', user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Send a new password reset code
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/send_password_reset', methods=['GET'])
@login_required
@admin_only
@update_last_seen
def password_reset_user():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"password_reset_user(): Missing user_id!")
        Event().log_event("Send Reset Fail", f"Missing user id!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"password_reset_user(): Invalid user user_id = '{user_id}'!")
        Event().log_event("Send Reset Fail", f"Invalid user user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Send reset
    # ----------------------------------------------------------- #
    if User().create_new_reset_code(user.email):
        app.logger.debug(f"password_reset_user(): Invalid user user_id = '{user_id}'!")
        Event().log_event("Send Reset Pass", f"Reset code sent to '{user.email}'.")
        flash("Reset code sent!")
    else:
        # Should never get here, but...
        app.logger.debug(f"password_reset_user(): User().create_new_reset_code failed, user_id = '{user_id}'!")
        Event().log_event("Send Reset Fail", f"User().create_new_reset_code failed, user_id = '{user_id}'!")
        flash("Sorry, something went wrong!")

    # Back to user page
    return redirect(url_for('user_page', user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Test SMS
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/test_sms', methods=['GET'])
@login_required
@admin_only
@update_last_seen
def test_sms():
    # ----------------------------------------------------------- #
    # Send SMS
    # ----------------------------------------------------------- #
    send_sms(current_user, "Test SMS")
    flash(f"An SMS has been sent to '{current_user.phone_number}'")

    # Back to user page
    return redirect(url_for('user_page', user_id=current_user.id))


# -------------------------------------------------------------------------------------------------------------- #
# Enable maps
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/enable_maps', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def enable_maps():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
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
    #  Need user
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(current_user.id)
    if not user:
        app.logger.debug(f"enable_maps(): Invalid user current_user.id = '{current_user.id}'!")
        Event().log_event("Enable Maps Fail", f"Invalid user current_user.id = '{current_user.id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    #  Validate against current_user's (admins) password
    # ----------------------------------------------------------- #
    if not user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"enable_maps(): Incorrect password for user_id = '{current_user.id}'!")
        Event().log_event("Enable Maps Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for '{current_user.name}'.")
        return redirect(url_for('admin_page', user_id=current_user.id))

    # ----------------------------------------------------------- #
    #  Enable Maps
    # ----------------------------------------------------------- #
    set_enable_maps()

    # Verify
    if maps_enabled():
        app.logger.debug(f"enable_maps(): Enabled Maps, current_user.id = '{current_user.id}'!")
        Event().log_event("Enable Maps Success", f"Enabled Maps, current_user.id = '{current_user.id}'.")
        flash("Maps enabled")
    else:
        app.logger.debug(f"enable_maps(): Failed to enable maps, current_user.id = '{current_user.id}'!")
        Event().log_event("Enable Maps Fail", f"Failed to enable maps, current_user.id = '{current_user.id}'.")
        flash("Sorry, something went wrong")

    # Back to user page
    return redirect(url_for('admin_page', user_id=current_user.id))


# -------------------------------------------------------------------------------------------------------------- #
# Disable maps
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/disable_maps', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def disable_maps():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
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
    #  Need user
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(current_user.id)
    if not user:
        app.logger.debug(f"disable_maps(): Invalid user current_user.id = '{current_user.id}'!")
        Event().log_event("Disable Maps Fail", f"Invalid user current_user.id = '{current_user.id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    #  Validate against current_user's (admins) password
    # ----------------------------------------------------------- #
    if not user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"disable_maps(): Incorrect password for user_id = '{current_user.id}'!")
        Event().log_event("Disable Maps Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for '{current_user.name}'.")
        return redirect(url_for('admin_page', user_id=current_user.id))

    # ----------------------------------------------------------- #
    #  Disable Maps
    # ----------------------------------------------------------- #
    set_disable_maps()

    # Verify
    if not maps_enabled():
        app.logger.debug(f"disable_maps(): Disabled Maps, current_user.id = '{current_user.id}'!")
        Event().log_event("Disable Maps Success", f"Disabled Maps, current_user.id = '{current_user.id}'.")
        flash("Maps disabled")
    else:
        app.logger.debug(f"disable_maps(): Failed to disable maps, current_user.id = '{current_user.id}'!")
        Event().log_event("Disable Maps Fail", f"Failed to disable maps, current_user.id = '{current_user.id}'.")
        flash("Sorry, something went wrong")

    # Back to user page
    return redirect(url_for('admin_page', user_id=current_user.id))