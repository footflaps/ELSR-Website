from flask import url_for, request, flash, redirect, abort
from flask_login import login_required, current_user
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import update_last_seen, logout_barred_user
from core.dB_events import Event
from core.db_social import Socials


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Sign up to social
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/social_am_coming', methods=['GET'])
@logout_barred_user
@update_last_seen
@login_required
def social_can():
    # ----------------------------------------------------------- #
    # Get params
    # ----------------------------------------------------------- #
    social_id = request.args.get('social_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not social_id:
        app.logger.debug(f"social_can(): Missing social_id!")
        Event().log_event("social_can() Fail", f"Missing social_id!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    social = Socials().one_social_id(social_id)
    if not social:
        app.logger.debug(f"social_can(): Failed to locate Social with social_id = '{social_id}'.")
        Event().log_event("social_can() Fail", f"Failed to Social with social_id = '{social_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check permissions
    # ----------------------------------------------------------- #
    # User must have write permission
    if not current_user.readwrite():
        app.logger.debug(f"social_can(): User not readwrite!")
        Event().log_event("social_can() Fail", f"User not readwrite!")
        flash("You don't have permission to sign up etc!")
        return abort(403)

    # Social must be subscribable
    if social.sign_up != "True":
        app.logger.debug(f"social_can(): Social doesn't have sign up, social_id = '{social_id}'.")
        Event().log_event("social_can() Fail", f"Social doesn't have sign up, social_id = '{social_id}'.")
        flash("This social isn't subscribable!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Check they haven't already signed up
    # ----------------------------------------------------------- #
    if social.attendees:
        attendees = json.loads(social.attendees)
    else:
        attendees = []

    # Their email should be in the list
    if current_user.email in attendees:
        # Should never happen, but...
        app.logger.debug(f"social_can(): Already signed up, social_id = '{social_id}'.")
        Event().log_event("social_can() Fail", f"Already signed up, social_id = '{social_id}'.")
        flash("Invalid option!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Add their email
    # ----------------------------------------------------------- #
    # Remove email
    attendees.append(current_user.email)
    # Push back to poll object as JSON string
    social.attendees = json.dumps(attendees)
    # Update in db
    social = Socials().add_social(social)
    # Did that work?
    if not social:
        # Should never happen, but...
        app.logger.debug(f"social_can(): Can't update social, social_id = '{social_id}'.")
        Event().log_event("social_can() Fail", f"Can't update social, social_id = '{social_id}'.")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Back to poll page
    # ----------------------------------------------------------- #

    return redirect(url_for(f'social', date=social.date, anchor=f"social_{social_id}"))


# -------------------------------------------------------------------------------------------------------------- #
# Remove sign up to social
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/social_not_coming', methods=['GET'])
@logout_barred_user
@update_last_seen
@login_required
def social_cant():
    # ----------------------------------------------------------- #
    # Get params
    # ----------------------------------------------------------- #
    social_id = request.args.get('social_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not social_id:
        app.logger.debug(f"social_cant(): Missing social_id!")
        Event().log_event("social_cant() Fail", f"Missing social_id!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    social = Socials().one_social_id(social_id)
    if not social:
        app.logger.debug(f"social_cant(): Failed to locate Social with social_id = '{social_id}'.")
        Event().log_event("social_cant() Fail", f"Failed to Social with social_id = '{social_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check permissions
    # ----------------------------------------------------------- #
    # User must have write permission
    if not current_user.readwrite():
        app.logger.debug(f"social_cant(): User not readwrite!")
        Event().log_event("social_cant() Fail", f"User not readwrite!")
        flash("You don't have permission to sign up etc!")
        return abort(403)

    # Social must be subscribable
    if social.sign_up != "True":
        app.logger.debug(f"social_cant(): Social doesn't have sign up, social_id = '{social_id}'.")
        Event().log_event("social_cant() Fail", f"Social doesn't have sign up, social_id = '{social_id}'.")
        flash("This social isn't subscribable!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Check they have a vote to remove
    # ----------------------------------------------------------- #
    if social.attendees:
        attendees = json.loads(social.attendees)
    else:
        attendees = []

    # Their email should be in the list
    if not current_user.email in attendees:
        # Should never happen, but...
        app.logger.debug(f"social_cant(): Can't remove non existent vote!")
        Event().log_event("social_cant() Fail", f"Can't remove non existent vote!")
        flash("Invalid option!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Remove their email
    # ----------------------------------------------------------- #
    # Remove email
    attendees.remove(current_user.email)
    # Push back to poll object as JSON string
    social.attendees = json.dumps(attendees)
    # Update in db
    social = Socials().add_social(social)
    # Did that work?
    if not social:
        # Should never happen, but...
        app.logger.debug(f"social_cant(): Can't update social, social_id = '{social_id}'.")
        Event().log_event("social_cant() Fail", f"Can't update social, social_id = '{social_id}'.")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Back to poll page
    # ----------------------------------------------------------- #

    return redirect(url_for(f'social', date=social.date, anchor=f"social_{social_id}"))
