from flask import request, abort, flash, redirect, url_for
from flask_login import current_user
from werkzeug import exceptions


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Import our Event class
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.user_repository import UserRepository
from core.database.repositories.event_repository import EventRepository

from core.decorators.user_decorators import admin_only, update_last_seen, login_required


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Delete a single Event
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/delete_event', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def delete_event():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    event_id = request.args.get('event_id', None)
    user_id = request.args.get('user_id', None)         # Optional (admin page doesn't know)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not event_id:
        app.logger.debug(f"delete_event(): Missing message_id!")
        EventRepository().log_event("Delete Event Fail", f"Missing event_id!")
        return abort(400)
    elif not user_id \
            and url_for("user_page") in request.referrer:
        # NB If we are jumping back to user_page, we must have a valid user_id
        app.logger.debug(f"delete_event(): Missing user_id!")
        EventRepository().log_event("Delete Event Fail", f"Missing user_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate id
    # ----------------------------------------------------------- #
    event = EventRepository().event_id(event_id)
    if not event:
        app.logger.debug(f"delete_event(): Can't locate event event_id = '{event_id}'.")
        EventRepository().log_event("Delete Event Fail", f"Can't locate event id = '{event_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Delete event
    # ----------------------------------------------------------- #
    if EventRepository().delete_event(event_id):
        flash("Event has been deleted")
    else:
        # Should never get here, but...
        app.logger.debug(f"delete_event(): Event().delete_event() failed, event_id = '{event_id}'")
        EventRepository().log_event("MDelete Event Fail", f"Failed to delete, event_id = '{event_id}'")
        flash("Sorry, something went wrong")

    # Back to calling page, which will either be:
    #   1. user_page
    #   2. admin_page
    # We want to jump back to the event table directly, which is a little involved.
    # The easiest way is to jump to the route handler for that page passing an flag for the table
    if url_for("user_page") in request.referrer:
        # Tell user page to jump straight to the event table using 'anchor'
        # NB user_page must have a valid user_id
        return redirect(url_for("user_page", user_id=user_id, anchor="eventLog"))
    elif url_for("admin_page") in request.referrer:
        # Tell admin page to jump straight to the event table using 'anchor'
        return redirect(url_for("admin_page", anchor="eventLog"))
    else:
        # Should never get here, but just in case, go to admin page
        return redirect(url_for("admin_page", anchor="eventLog"))


# -------------------------------------------------------------------------------------------------------------- #
# Delete a block of events
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/delete_events', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def delete_events():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    days = request.args.get('days', None)
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
    if not days:
        app.logger.debug(f"delete_events(): Missing days!")
        EventRepository().log_event("Delete Events Fail", f"Missing days!")
        return abort(400)
    elif not user_id:
        app.logger.debug(f"delete_events(): Missing user_id!")
        EventRepository().log_event("Delete Events Fail", f"Missing user_id!")
        return abort(400)
    elif not password:
        app.logger.debug(f"delete_events(): Missing password!")
        EventRepository().log_event("Delete Events Fail", f"Missing password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate user_id (unless it's admin) & Confirm
    # ----------------------------------------------------------- #
    if user_id != "admin":
        user = UserRepository().find_user_from_id(user_id)
        if not user:
            app.logger.debug(f"delete_events(): Invalid user_id = '{user_id}'.")
            EventRepository().log_event("Delete Events Fail", f"Invalid user_id = '{user_id}'.")
            return abort(404)

    # ----------------------------------------------------------- #
    # Validate current_user's (admins) password
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"delete_events(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        EventRepository().log_event("Delete Events Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        if user_id == "admin":
            # Back to Admin page
            return redirect(url_for('admin_page', anchor="eventLog"))
        else:
            # Back to user page
            return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Delete events
    # ----------------------------------------------------------- #
    # If user_id = "admin" we're deleting all events from the admin page, otherwise
    # we're on the user page and just deleting their events
    if user_id.lower() == "admin":
        app.logger.debug(f"delete_events(): We think we're called from admin, so delete events for all users.")
        if EventRepository().delete_events_all_days(days):
            flash("Messages deleted!")
        else:
            # Should never get here, but...
            app.logger.debug(f"delete_events(): Event().delete_events_all_days() failed, days = '{days}'.")
            EventRepository().log_event("Delete Events Fail", f"days = '{days}'")
    else:
        app.logger.debug(f"delete_events(): Delete '{days}' days of events for user '{user.email}'.")
        if EventRepository().delete_events_email_days(user.email, days):
            flash("Messages deleted!")
        else:
            # Should never get here, but...
            app.logger.debug(f"delete_events(): Event().delete_events_email_days() failed, "
                             f"days = '{days}', email = '{user.email}'.")
            EventRepository().log_event("Delete Events Fail", f"Days = '{days}', email = '{user.email}'")

    # Back to calling page, which will either be:
    #   1. user_page
    #   2. admin_page
    # We want to jump back to the event table directly, which is a little involved.
    # The easiest way is to jump to the route handler for that page passing an flag for the table
    if url_for("user_page") in request.referrer:
        # Tell user page to jump straight to the event table using 'anchor'
        # NB user_page must have a valid user_id
        return redirect(url_for("user_page", user_id=user_id, anchor="eventLog"))
    elif url_for("admin_page") in request.referrer:
        # Tell admin page to jump straight to the event table using 'anchor'
        return redirect(url_for("admin_page", anchor="eventLog"))
    else:
        # Should never get here, but just in case go to Admin page
        return redirect(url_for("admin_page", anchor="eventLog"))


# -------------------------------------------------------------------------------------------------------------- #
# Delete all 404 events
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/delete_404s', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def delete_404s():
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
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not password:
        app.logger.debug(f"delete_404s(): Missing password!")
        EventRepository().log_event("Delete 404s Fail", f"Missing password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate user_id and confirm
    # ----------------------------------------------------------- #
    if not current_user.admin:
        app.logger.debug(f"delete_404s(): Invalid user_id = '{current_user.id}'.")
        EventRepository().log_event("Delete 404s Fail", f"Invalid user_id = '{current_user.id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Validate current_user's (admins) password
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"delete_events(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        EventRepository().log_event("Delete Events Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        # Back to Admin page
        return redirect(url_for('admin_page', anchor="eventLog"))

    # ----------------------------------------------------------- #
    # Delete 404 events
    # ----------------------------------------------------------- #
    if EventRepository().delete_all_404s():
        flash("404 Events deleted!")
    else:
        # Should never get here, but...
        app.logger.debug(f"delete_404s(): Event().delete_all_404s() failed.")
        EventRepository().log_event("Delete 404s Fail", f"Event().delete_all_404s() failed.")

    # Back to Admin page
    return redirect(url_for("admin_page", anchor="eventLog"))

