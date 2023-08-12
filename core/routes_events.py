from flask import request, abort, flash, redirect, url_for
from flask_login import login_required, current_user


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Import our Event class
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_events import Event
from core.db_users import admin_only
from core.db_users import User, update_last_seen


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

@app.route('/delete_event', methods=['GET'])
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
        Event().log_event("Delete Event Fail", f"Missing event_id!")
        return abort(400)
    elif not user_id \
            and "user_page" in request.referrer:
        # NB If we are jumping back to user_page, we must have a valid user_id
        app.logger.debug(f"delete_event(): Missing user_id!")
        Event().log_event("Delete Event Fail", f"Missing user_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate id
    # ----------------------------------------------------------- #
    event = Event().event_id(event_id)
    if not event:
        app.logger.debug(f"delete_event(): Can't locate event event_id = '{event_id}'.")
        Event().log_event("Delete Event Fail", f"Can't locate event id = '{event_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Delete event
    # ----------------------------------------------------------- #
    if Event().delete_event(event_id):
        flash("Event has been deleted")
    else:
        # Should never get here, but...
        app.logger.debug(f"delete_event(): Event().delete_event() failed, event_id = '{event_id}'")
        Event().log_event("MDelete Event Fail", f"Failed to delete, event_id = '{event_id}'")
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
        # Should never get here, but just in case
        return redirect(request.referrer)


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
    confirm = request.form['confirm_ev']
    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if confirm == "":
        confirm = " "

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not days:
        app.logger.debug(f"delete_events(): Missing days!")
        Event().log_event("Delete Events Fail", f"Missing days!")
        return abort(400)
    elif not user_id:
        app.logger.debug(f"delete_events(): Missing user_id!")
        Event().log_event("Delete Events Fail", f"Missing user_id!")
        return abort(400)
    elif not confirm:
        app.logger.debug(f"delete_events(): Missing confirm!")
        Event().log_event("Delete Events Fail", f"Missing confirm!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate user_id (unless it's admin) & Confirm
    # ----------------------------------------------------------- #
    if user_id != "admin":
        user = User().find_user_from_id(user_id)
        if not user:
            app.logger.debug(f"delete_events(): Invalid user_id = '{user_id}'.")
            Event().log_event("Delete Events Fail", f"Invalid user_id = '{user_id}'.")
            return abort(404)

    if confirm != "DELETE":
        app.logger.debug(f"delete_events(): Delete wasn't confirmed, confirm = '{confirm}'!")
        Event().log_event("Delete events FAIL", f"Delete wasn't confirmed, confirm = '{confirm}'!")
        flash(f"Delete wasn't confirmed '{confirm}'.")
        if user_id == "admin":
            # Back to Admin page
            return redirect(url_for('admin_page'))
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
        if Event().delete_events_all_days(days):
            flash("Messages deleted!")
        else:
            # Should never get here, but...
            app.logger.debug(f"delete_events(): Event().delete_events_all_days() failed, days = '{days}'.")
            Event().log_event("Delete Events Fail", f"days = '{days}'")
    else:
        app.logger.debug(f"delete_events(): Delete '{days}' days of events for user '{user.email}'.")
        if Event().delete_events_email_days(user.email, days):
            flash("Messages deleted!")
        else:
            # Should never get here, but...
            app.logger.debug(f"delete_events(): Event().delete_events_email_days() failed, "
                             f"days = '{days}', email = '{user.email}'.")
            Event().log_event("Delete Events Fail", f"Days = '{days}', email = '{user.email}'")

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
        # Should never get here, but just in case
        return redirect(request.referrer)


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
    confirm = request.form['confirm_404']
    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if confirm == "":
        confirm = " "

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not confirm:
        app.logger.debug(f"delete_404s(): Missing confirm!")
        Event().log_event("Delete 404s Fail", f"Missing confirm!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate user_id and confirm
    # ----------------------------------------------------------- #
    if not current_user.admin():
        app.logger.debug(f"delete_404s(): Invalid user_id = '{current_user.id}'.")
        Event().log_event("Delete 404s Fail", f"Invalid user_id = '{current_user.id}'.")
        return abort(403)
    if confirm != "DELETE":
        flash(f"Delete not confirmed: '{confirm}'")
        app.logger.debug(f"delete_404s(): Delete not confirmed: '{confirm}'.")
        Event().log_event("Delete 404s Fail", f"Delete not confirmed: '{confirm}'.")
        # Back to Admin page
        return redirect(url_for("admin_page"))

    # ----------------------------------------------------------- #
    # Delete 404 events
    # ----------------------------------------------------------- #
    if Event().delete_all_404s():
        flash("404 Events deleted!")
    else:
        # Should never get here, but...
        app.logger.debug(f"delete_404s(): Event().delete_all_404s() failed.")
        Event().log_event("Delete 404s Fail", f"Event().delete_all_404s() failed.")

    # Back to Admin page
    return redirect(url_for("admin_page", anchor="eventLog"))

