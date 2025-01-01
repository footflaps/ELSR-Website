from flask import url_for, request, flash, redirect, abort, Response
from flask_login import current_user
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.event_repository import EventRepository
from core.database.repositories.social_repository import SocialRepository

from core.decorators.user_decorators import update_last_seen, logout_barred_user, login_required, rw_required


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
@rw_required
def social_can() -> Response:
    # ----------------------------------------------------------- #
    # Get params
    # ----------------------------------------------------------- #
    social_id = request.args.get('social_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not social_id:
        app.logger.debug(f"social_can(): Missing social_id!")
        EventRepository().log_event("social_can() Fail", f"Missing social_id!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    social = SocialRepository().one_by_id(social_id)
    if not social:
        app.logger.debug(f"social_can(): Failed to locate Social with social_id = '{social_id}'.")
        EventRepository().log_event("social_can() Fail", f"Failed to Social with social_id = '{social_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check permissions
    # ----------------------------------------------------------- #
    # Social must be subscribable
    if social.sign_up != "True":
        app.logger.debug(f"social_can(): Social doesn't have sign up, social_id = '{social_id}'.")
        EventRepository().log_event("social_can() Fail", f"Social doesn't have sign up, social_id = '{social_id}'.")
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
        EventRepository().log_event("social_can() Fail", f"Already signed up, social_id = '{social_id}'.")
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
    social = SocialRepository().add_social(social)
    # Did that work?
    if not social:
        # Should never happen, but...
        app.logger.debug(f"social_can(): Can't update social, social_id = '{social_id}'.")
        EventRepository().log_event("social_can() Fail", f"Can't update social, social_id = '{social_id}'.")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Back to poll page
    # ----------------------------------------------------------- #

    return redirect(url_for(f'display_socials', date=social.date, anchor=f"social_{social_id}"))


# -------------------------------------------------------------------------------------------------------------- #
# Remove sign up to social
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/social_not_coming', methods=['GET'])
@logout_barred_user
@update_last_seen
@login_required
@rw_required
def social_cant() -> Response:
    # ----------------------------------------------------------- #
    # Get params
    # ----------------------------------------------------------- #
    social_id = request.args.get('social_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not social_id:
        app.logger.debug(f"social_cant(): Missing social_id!")
        EventRepository().log_event("social_cant() Fail", f"Missing social_id!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    social = SocialRepository().one_by_id(social_id)
    if not social:
        app.logger.debug(f"social_cant(): Failed to locate Social with social_id = '{social_id}'.")
        EventRepository().log_event("social_cant() Fail", f"Failed to Social with social_id = '{social_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check permissions
    # ----------------------------------------------------------- #
    # Social must be subscribable
    if social.sign_up != "True":
        app.logger.debug(f"social_cant(): Social doesn't have sign up, social_id = '{social_id}'.")
        EventRepository().log_event("social_cant() Fail", f"Social doesn't have sign up, social_id = '{social_id}'.")
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
    if current_user.email not in attendees:
        # Should never happen, but...
        app.logger.debug(f"social_cant(): Can't remove non existent vote!")
        EventRepository().log_event("social_cant() Fail", f"Can't remove non existent vote!")
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
    social = SocialRepository().add_social(social)
    # Did that work?
    if not social:
        # Should never happen, but...
        app.logger.debug(f"social_cant(): Can't update social, social_id = '{social_id}'.")
        EventRepository().log_event("social_cant() Fail", f"Can't update social, social_id = '{social_id}'.")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Back to poll page
    # ----------------------------------------------------------- #

    return redirect(url_for(f'display_socials', date=social.date, anchor=f"social_{social_id}"))
