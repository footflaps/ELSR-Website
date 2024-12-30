from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user
from werkzeug import exceptions
from datetime import datetime
import os
import subprocess
from threading import Thread


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, is_mobile, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our own Classes
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.db_users import User, admin_only, update_last_seen, SUPER_ADMIN_USER_ID, login_required
from core.database.repositories.message_repository import MessageRepository, ADMIN_EMAIL
from core.database.repositories.event_repository import EventRepository
from core.database.repositories.calendar_repository import CalendarRepository
from core.database.repositories.social_repository import SocialRepository, SOCIAL_DB_PRIVATE
from core.subs_email_sms import send_sms, get_twilio_balance, send_message_notification_email, email_ride_alert_summary
from core.subs_google_maps import maps_enabled, get_current_map_count, map_limit_by_day, graph_map_counts
from core.database.repositories.blog_repository import BlogRepository as Blog
from core.database.repositories.classifieds_repository import ClassifiedRepository
from core.database.repositories.cafe_comment_repository import CafeCommentRepository


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

DEFAULT_EVENT_DAYS = 7


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Size of key files and directories
# -------------------------------------------------------------------------------------------------------------- #
def get_file_sizes():
    # Return this
    details = []

    # ----------------------------------------------------------- #
    # Scan databases
    # ----------------------------------------------------------- #
    if os.path.exists("/home/ben_freeman_eu/elsr_website/ELSR-Website/env_vars.py"):
        db_dir = "/home/ben_freeman_eu/elsr_website/ELSR-Website/instance/"
    else:
        db_dir = "../instance/"

    for filename in os.listdir(db_dir):
        f = os.path.join(db_dir, filename)
        # checking if it is a file
        if os.path.isfile(f):
            if f.endswith(".db"):
                details.append({
                    'name': os.path.basename(f),
                    'type': "file",
                    'size': os.stat(f).st_size / (1024 * 1024)
                })

    # ----------------------------------------------------------- #
    # Key directories
    # ----------------------------------------------------------- #
    if os.path.exists("/home/ben_freeman_eu/elsr_website/ELSR-Website/env_vars.py"):
        # On server
        dirs = ["/home/ben_freeman_eu/elsr_website/ELSR-Website/instance",
                "/home/ben_freeman_eu/elsr_website/ELSR-Website/core/gpx",
                "/home/ben_freeman_eu/elsr_website/ELSR-Website/core/config",
                "/home/ben_freeman_eu/elsr_website/ELSR-Website/core/ics",
                "/home/ben_freeman_eu/elsr_website/ELSR-Website/core/static/img/cafe_photos"]
    else:
        # On laptop
        dirs = ["../instance", "../core/gpx", "../core/config", "../core/ics", "../core/static/img/cafe_photos"]

    for dir in dirs:
        size = 0
        for path, dirs, files in os.walk(dir):
            for f in files:
                fp = os.path.join(path, f)
                size += os.path.getsize(fp)
            details.append({
                'name': f"{os.path.basename(dir)}/",
                'type': "dir",
                'size': size / (1024 * 1024)
            })

    return details


# -------------------------------------------------------------------------------------------------------------- #
# Free Space on server
# -------------------------------------------------------------------------------------------------------------- #
def get_free_space():
    # ----------------------------------------------------------- #
    # Free space
    # ----------------------------------------------------------- #
    if os.path.exists("/home/ben_freeman_eu/elsr_website/ELSR-Website/env_vars.py"):
        # On server
        result = subprocess.run(['/usr/bin/df', '-h', '/dev/root'], stdout=subprocess.PIPE)
        output = result.stdout.decode('utf-8')
        lines = output.split('\n')
        data = lines[1].split()
        used_per = float(data[4].replace('%',''))
        free_per = 100 - used_per
        return free_per
    else:
        return None


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
        EventRepository().log_event("Admin Page Fail", f"on Admin access, user_id = '{current_user.id}'!")
        return abort(403)

    # ----------------------------------------------------------- #
    # List of all events for relevant period (for admin page table)
    # ----------------------------------------------------------- #
    # Valid values for event_period are:
    #   1.  None - in which case use default value
    #   2.  An integer (number of days)
    #   3.  "all" - in which case show all events
    if not event_period:
        events = EventRepository().all_events_days(DEFAULT_EVENT_DAYS)
        days = DEFAULT_EVENT_DAYS
    elif event_period == "all":
        events = EventRepository().all_events()
        days = "all"
    else:
        events = EventRepository().all_events_days(int(event_period))
        days = int(event_period)

    # ----------------------------------------------------------- #
    # List of all users (for admin page table)
    # ----------------------------------------------------------- #
    admins = User().all_admins()
    non_admins = User().all_non_admins()

    # Split users into two camps
    trusted_users = []
    untrusted_users = []
    for user in non_admins:

        # Add readable timestamps
        if user.verification_code_timestamp:
            user.verification_code_timestamp = \
                datetime.utcfromtimestamp(user.verification_code_timestamp).strftime('%d%m%Y %H:%M:%S')
        # Split by properties
        if user.readwrite() and \
                not user.blocked():
            trusted_users.append(user)
        else:
            untrusted_users.append(user)

    # ----------------------------------------------------------- #
    # All messages for Admin (for admin page table)
    # ----------------------------------------------------------- #
    messages = MessageRepository().all_messages_to_email(ADMIN_EMAIL)

    # ----------------------------------------------------------- #
    # All scheduled calendar events (routes)
    # ----------------------------------------------------------- #
    rides = CalendarRepository().all_calendar()

    # ----------------------------------------------------------- #
    # All scheduled social events
    # ----------------------------------------------------------- #
    socials = SocialRepository().all()
    for social in socials:
        if social.privacy == SOCIAL_DB_PRIVATE:
            social.private = True
        else:
            social.private = False

    # ----------------------------------------------------------- #
    # Blog posts
    # ----------------------------------------------------------- #
    blogs = Blog().all()
    for blog in blogs:

        # 1. Human-readable date
        if blog.date_unix:
            blog.date = datetime.utcfromtimestamp(blog.date_unix).strftime('%d %b %Y')

    # ----------------------------------------------------------- #
    # All classifieds
    # ----------------------------------------------------------- #
    classifieds = ClassifiedRepository().all()

    # ----------------------------------------------------------- #
    # All cafe comments
    # ----------------------------------------------------------- #
    comments = CafeCommentRepository().all()

    # ----------------------------------------------------------- #
    # Twilio balance
    # ----------------------------------------------------------- #
    twilio_balance = get_twilio_balance()

    # ----------------------------------------------------------- #
    # Google Maps Status
    # ----------------------------------------------------------- #
    map_status = maps_enabled()
    map_count = get_current_map_count()
    map_cost_ukp = 0.0055 * map_count
    today_str = datetime.today().strftime("%A")
    map_limit = map_limit_by_day(today_str)
    # Get graph dataset of map counts
    dataset = graph_map_counts()

    # ----------------------------------------------------------- #
    # Server stats
    # ----------------------------------------------------------- #
    # This is file and directory sizes
    files = get_file_sizes()
    # This is free space on the server
    free_per = get_free_space()

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
    # Who is getting email alerts
    # ----------------------------------------------------------- #
    email_alerts = email_ride_alert_summary()

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

    # If Admin is changing event view, jump straight to events section
    if event_period:
        anchor = "eventLog"

    # Render page
    return render_template("admin_page.html",  year=current_year, admins=admins, trusted_users=trusted_users,
                           messages=messages, events=events, days=days, mobile=is_mobile(), socials=socials,
                           rides=rides, twilio_balance=twilio_balance, map_status=map_status, blogs=blogs,
                           map_count=map_count, map_cost_ukp=map_cost_ukp, map_limit=map_limit,
                           files=files, free_per=free_per, untrusted_users=untrusted_users, classifieds=classifieds,
                           dataset=dataset, live_site=live_site(), anchor=anchor, email_alerts=email_alerts,
                           comments=comments)


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
        EventRepository().log_event("Make Admin Fail", f"Missing user_id")
        return abort(400)
    elif not password:
        app.logger.debug(f"make_admin(): Missing Admin's password!")
        EventRepository().log_event("Make Admin Fail", f"Missing Admin's password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)

    # Check id is valid
    if not user:
        # Can't find that user
        app.logger.debug(f"make_admin(): FAILED to locate user user_id = '{user_id}'.")
        EventRepository().log_event("Make Admin Fail", f"FAILED to locate user user_id = '{user_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Validate password against current_user's (admins)
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"make_admin(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        EventRepository().log_event("Make Admin Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Restrict access - only Super Admin can do this
    # ----------------------------------------------------------- #
    if current_user.id != SUPER_ADMIN_USER_ID:
        # Failed authentication
        app.logger.debug(f"make_admin(): Rejected request from '{current_user.email}' as no permissions!")
        EventRepository().log_event(f"Make Admin Fail", f"Rejected request as no permissions. user_id = '{user_id}'")
        return abort(403)

    # ----------------------------------------------------------- #
    # Admins must have validated phone number for 2FA login
    # ----------------------------------------------------------- #
    if not user.has_valid_phone_number():
        # Can't make admin
        flash("Sorry, user doesn't have a validated mobile number, so can't use 2FA which is mandatory for Admins!")
        app.logger.debug(f"make_admin(): Rejected request to made user_id = '{user_id}' admin as doesn't have 2FA.")
        EventRepository().log_event(f"Make Admin Fail", f"Rejected request to made user_id = '{user_id}' "
                                              f"admin as doesn't have 2FA.")
        # Back to calling page
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Make admin
    # ----------------------------------------------------------- #
    if User().make_admin(user_id):
        # Success
        app.logger.debug(f"make_admin(): Success, user_id = '{user_id}'.")
        EventRepository().log_event(f"Make Admin Success", f"User is now Admin! user_id = '{user_id}'.")
        flash(f"{user.name} is now an Admin.")
    else:
        # Should never get here!
        app.logger.debug(f"make_admin(): User().make_admin() failed, user_id = '{user_id}.")
        EventRepository().log_event(f"Make Admin Fail", f"User().make_admin() failed, user_id = '{user_id}'.")
        flash("Sorry, something went wrong!")

    # Back to calling page
    return redirect(url_for('user_page', user_id=user_id))


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
        EventRepository().log_event("unMake Admin Fail", f"Missing user_id")
        return abort(400)
    elif not password:
        app.logger.debug(f"unmake_admin(): Missing Admin's password!")
        EventRepository().log_event("unMake Admin Fail", f"Missing Admin's password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)

    # Check id is valid
    if not user:
        app.logger.debug(f"unmake_admin(): FAILED to locate user user_id = '{user_id}'.")
        EventRepository().log_event("unMake Admin Fail", f"FAILED to locate user user_id = '{user_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Validate password against current_user's (admins)
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"unmake_admin(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        EventRepository().log_event("unMake Admin Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Restrict access - only Super Admin can do this
    # ----------------------------------------------------------- #
    if current_user.id != SUPER_ADMIN_USER_ID:
        # Failed authentication
        app.logger.debug(f"unmake_admin(): Rejected request from '{current_user.email}' as no permissions!")
        EventRepository().log_event("unMake Admin Fail", f"Rejected request as no permissions!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Make admin
    # ----------------------------------------------------------- #
    if User().unmake_admin(user_id):
        # Success
        app.logger.debug(f"unmake_admin(): Success with user_id = '{user_id}'.")
        EventRepository().log_event("unMake Admin Success", f"User '{user.email}' is no longer an Admin!, user_id = '{user_id}'.")
        flash(f"{user.name} is no longer an Admin.")
    else:
        # Should never get here!
        app.logger.debug(f"unmake_admin(): User().unmake_admin() failed with user_id = '{user_id}'.")
        EventRepository().log_event("unMake Admin Fail", f"User().unmake_admin() failed with user_id = '{user_id}'")
        flash("Sorry, something went wrong!")

    # Back to calling page
    return redirect(url_for('user_page', user_id=user_id))


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
        EventRepository().log_event("Block User Fail", f"missing user id.")
        abort(400)
    elif not password:
        app.logger.debug(f"block_user(): Missing Admin's password!")
        EventRepository().log_event("Block User Fail", f"Missing Admin's password!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"block_user(): Invalid user user_id = '{user_id}'!")
        EventRepository().log_event("Block User Fail", f"invalid user user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Validate password against current_user's (admins)
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"block_user(): Block failed, incorrect password for user_id = '{current_user.id}'!")
        EventRepository().log_event("Block User Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Can't block yourself nor an admin
    # ----------------------------------------------------------- #
    if current_user.id == user.id:
        app.logger.debug(f"block_user(): Block failed, admin can't block themselves, user_id = '{current_user.id}'.")
        EventRepository().log_event("Block User Fail", f"Admin can't block themselves, user_id = '{current_user.id}'.")
        flash(f"You can't block yourself!")
        return redirect(url_for('user_page', user_id=user_id))
    if user.admin():
        app.logger.debug(f"block_user(): Block failed, can't block Admin, user_id = '{current_user.id}'.")
        EventRepository().log_event("Block User Fail", f"Can't block Admin, user_id = '{current_user.id}'.")
        flash(f"You can't block an Admin!")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Block user
    # ----------------------------------------------------------- #
    if User().block_user(user_id):
        app.logger.debug(f"block_user(): User '{user_id}' is now blocked.")
        EventRepository().log_event("Block User Success", f"User '{user_id}' is now blocked.")
        flash("User Blocked.")
    else:
        # Should never get here, but...
        app.logger.debug(f"block_user(): User().block_user() failed, user_id = '{user_id}'!")
        EventRepository().log_event("Block User Fail", f"User().block_user() failed, user_id = '{user_id}'!")
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
        EventRepository().log_event("unBlock User Fail", f"missing user id.")
        abort(400)
    elif not password:
        app.logger.debug(f"unblock_user(): Missing Admin's password!")
        EventRepository().log_event("unBlock User Fail", f"Missing Admin's password!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"unblock_user(): Invalid user user_id = '{user_id}'!")
        EventRepository().log_event("unBlock User Fail", f"invalid user user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Validate password against current_user's (admins)
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"unblock_user(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        EventRepository().log_event("unBlock User Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Can't block yourself nor an admin
    # ----------------------------------------------------------- #
    if current_user.id == user.id:
        app.logger.debug(
            f"block_user(): ubBlock failed, admin can't unblock themselves, user_id = '{current_user.id}'.")
        EventRepository().log_event("unBlock User Fail", f"Admin can't unblock themselves, user_id = '{current_user.id}'.")
        flash(f"You can't unblock yourself!")
        return redirect(url_for('user_page', user_id=user_id))
    if user.admin():
        app.logger.debug(f"unblock_user(): unBlock failed, can't block Admin, user_id = '{current_user.id}'.")
        EventRepository().log_event("unBlock User Fail", f"Can't unblock Admin, user_id = '{current_user.id}'.")
        flash(f"You can't unblock an Admin!")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Unblock user
    # ----------------------------------------------------------- #
    if User().unblock_user(user_id):
        app.logger.debug(f"unblock_user(): User '{user_id}' is now unblocked.")
        EventRepository().log_event("unBlock User Success", f"User '{user_id}' is now unblocked.")
        flash("User unblocked.")
    else:
        # Should never get here, but...
        app.logger.debug(f"unblock_user(): User().unblock_user() failed, user_id = '{user_id}'!")
        EventRepository().log_event("unBlock User Fail", f"User().unblock_user() failed, user_id = '{user_id}'!")
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
        EventRepository().log_event("ReadWrite Fail", f"Missing user id")
        abort(400)
    elif not password:
        app.logger.debug(f"user_readwrite(): Missing user password!")
        EventRepository().log_event("ReadWrite Fail", f"Missing user password")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"user_readwrite(): Invalid user user_id = '{user_id}'!")
        EventRepository().log_event("ReadWrite Fail", f"Invalid user user_id = '{user_id}'!")
        abort(404)

    # ----------------------------------------------------------- #
    # Can't edit yourself nor an admin
    # ----------------------------------------------------------- #
    if current_user.id == user.id:
        app.logger.debug(f"user_readwrite(): ubBlock failed, admin can't unblock themselves, user_id = '{user_id}'.")
        EventRepository().log_event("ReadWrite Fail", f"Admin can't unblock themselves, user_id = '{user_id}'.")
        flash(f"You can't unblock yourself!")
        return redirect(url_for('user_page', user_id=user_id))
    if user.admin():
        app.logger.debug(f"user_readwrite(): unBlock failed, can't block Admin, user_id = '{user_id}'.")
        EventRepository().log_event("ReadWrite Fail", f"Can't unblock Admin, user_id = '{user_id}'.")
        flash(f"You can't unblock an Admin!")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    #  Validate against current_user's (admins) password
    # ----------------------------------------------------------- #
    if not user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"user_readwrite(): Incorrect password for user_id = '{current_user.id}'!")
        EventRepository().log_event("ReadWrite Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for '{current_user.name}'.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Set Read Write permission
    # ----------------------------------------------------------- #
    if User().set_readwrite(user_id):
        app.logger.debug(f"user_readwrite(): Success, user can now write, user.email = '{user.email}'.")
        EventRepository().log_event("ReadWrite Success", f"User can now write, user.email = '{user.email}'.")
        flash(f"User '{user.name}' now has Write permissions.")
        message = MessageRepository().send_readwrite_message(user.email)
        Thread(target=send_message_notification_email, args=(message, user,)).start()
        return redirect(url_for('user_page', user_id=user_id))
    else:
        # Should never get here, but...
        app.logger.debug(f"user_readwrite(): User().set_readwrite() failed for user.email = '{user.email}'.")
        EventRepository().log_event("ReadWrite Fail", f"User().set_readwrite() failed for user.email = '{user.email}'.")
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
        EventRepository().log_event("ReadOnly Fail", f"Missing user id")
        abort(400)
    elif not password:
        app.logger.debug(f"user_readonly(): Missing user password!")
        EventRepository().log_event("ReadOnly Fail", f"Missing user password")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"user_readonly(): Invalid user user_id = '{user_id}'!")
        EventRepository().log_event("ReadOnly Fail", f"Invalid user user_id = '{user_id}'!")
        abort(404)

    # ----------------------------------------------------------- #
    # Can't edit yourself nor an admin
    # ----------------------------------------------------------- #
    if current_user.id == user.id:
        app.logger.debug(f"user_readonly(): ubBlock failed, admin can't unblock themselves, '{current_user.email}'.")
        EventRepository().log_event("ReadOnly Fail", f"Admin can't unblock themselves, '{current_user.email}'.")
        flash(f"You can't unblock yourself!")
        return redirect(url_for('user_page', user_id=user_id))
    if user.admin():
        app.logger.debug(f"user_readonly(): unBlock failed, can't block Admin, "
                         f"'{current_user.email}' blocking '{user.email}'.")
        EventRepository().log_event("ReadOnly Fail", f"Can't unblock Admin, '{current_user.email}' blocking '{user.email}'.")
        flash(f"You can't unblock an Admin!")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    #  Validate against current_user's (admins) password
    # ----------------------------------------------------------- #
    if not user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"user_readonly(): Incorrect password for '{current_user.email}'!")
        EventRepository().log_event("ReadOnly Fail", f"Incorrect password for '{current_user.email}'!")
        flash(f"Incorrect password for '{current_user.name}'.")
        return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Set Read Only permission
    # ----------------------------------------------------------- #
    if User().set_readonly(user_id):
        app.logger.debug(f"user_readonly(): Success, user is Readonly, user.email = '{user.email}'.")
        EventRepository().log_event("ReadOnly Success", f"User is Readonly, user.email = '{user.email}'.")
        flash(f"User '{user.name}' is now Read ONLY.")
        message = MessageRepository().send_readonly_message(user.email)
        Thread(target=send_message_notification_email, args=(message, user,)).start()
        return redirect(url_for('user_page', user_id=user_id))
    else:
        # Should never get here, but...
        app.logger.debug(f"user_readonly(): User().set_readonly() failed for user.email = '{user.email}'.")
        EventRepository().log_event("ReadOnly Fail", f"User().set_readonly() failed for user.email = '{user.email}'.")
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
        EventRepository().log_event("Send Verify Fail", f"Missing user_id.")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"reverify_user(): Invalid user user_id = '{user_id}'!")
        EventRepository().log_event("Send Verify Fail", f"Invalid user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Send verification code
    # ----------------------------------------------------------- #
    if User().create_new_verification(user_id):
        app.logger.debug(f"reverify_user(): Verification code sent user_id = '{user_id}'.")
        EventRepository().log_event("Send Verify Pass", f"Verification code sent user_id = '{user_id}'.")
        flash("Verification code sent!")
    else:
        # Should never get here, but...
        app.logger.debug(f"reverify_user(): User().create_new_verification() failed, user_id = '{user_id}'!")
        EventRepository().log_event("Send Verify Fail", f"User().create_new_verification() failed, user_id = '{user_id}'!")
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
        EventRepository().log_event("Send Reset Fail", f"Missing user id!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"password_reset_user(): Invalid user user_id = '{user_id}'!")
        EventRepository().log_event("Send Reset Fail", f"Invalid user user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Send reset
    # ----------------------------------------------------------- #
    if User().create_new_reset_code(user.email):
        app.logger.debug(f"password_reset_user(): Invalid user user_id = '{user_id}'!")
        EventRepository().log_event("Send Reset Pass", f"Reset code sent to '{user.email}'.")
        flash("Reset code sent!")
    else:
        # Should never get here, but...
        app.logger.debug(f"password_reset_user(): User().create_new_reset_code failed, user_id = '{user_id}'!")
        EventRepository().log_event("Send Reset Fail", f"User().create_new_reset_code failed, user_id = '{user_id}'!")
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

