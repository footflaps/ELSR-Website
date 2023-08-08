from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, current_user, logout_user, login_required, fresh_login_required
from datetime import date
from werkzeug import exceptions


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, is_mobile


# -------------------------------------------------------------------------------------------------------------- #
# Import our own Classes
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, admin_only, update_last_seen, SUPER_ADMIN_USER_ID
from core.db_messages import Message, ADMIN_EMAIL
from core.dB_events import Event


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
                               messages=messages, events=events, days=days, mobile=is_mobile(), anchor="eventLog")
    else:
        # No jumping, just display the page from the top
        return render_template("admin_page.html", year=current_year, admins=admins, non_admins=non_admins,
                               messages=messages, events=events, days=days, mobile=is_mobile())


# -------------------------------------------------------------------------------------------------------------- #
# Make a user admin
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/make_admin/<int:user_id>', methods=['GET'])
@login_required
@admin_only
@update_last_seen
def make_admin(user_id):
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    confirmation = request.args.get('admin_confirm', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"make_admin(): Missing user_id!.")
        Event().log_event("Make Admin Fail", f"Missing user_id")
        return abort(400)
    elif not confirmation:
        app.logger.debug(f"make_admin(): Missing confirmation!.")
        Event().log_event("Make Admin Fail", f"Missing confirmation")
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

    if confirmation != "ADMIN":
        # Failed authentication
        app.logger.debug(f"make_admin(): Rejected request as no confirmation, user_id = '{user_id}'.")
        Event().log_event("Make Admin Fail", f"Rejected request as no confirmation, user_id = '{user_id}'")
        flash("Admin was not confirmed!")
        return redirect(request.referrer)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if current_user.id != SUPER_ADMIN_USER_ID:
        # Failed authentication
        app.logger.debug(f"make_admin(): Rejected request from '{current_user.email}' as no permissions!")
        Event().log_event(f"Make Admin Fail", f"Rejected request as no permissions. user_id = '{user_id}'")
        return abort(403)

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

@app.route('/unmake_admin/<int:user_id>', methods=['GET'])
@login_required
@admin_only
@update_last_seen
def unmake_admin(user_id):
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    confirmation = request.args.get('unadmin_confirm', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"unmake_admin(): Missing user_id!.")
        Event().log_event("unMake Admin Fail", f"Missing user_id")
        return abort(400)
    elif not confirmation:
        app.logger.debug(f"unmake_admin(): Missing confirmation")
        Event().log_event("unMake Admin Fail", f"Missing confirmation")
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

    if confirmation != "REMOVE":
        # Failed authentication
        app.logger.debug(f"unmake_admin(): Invalid confirmation for user_id = '{user_id}'.")
        Event().log_event("unMake Admin Fail", f"Invalid confirmation for user_id = '{user_id}'.")
        flash("Admin was not confirmed properly!")
        return redirect(request.referrer)

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




