from flask import url_for, request, flash, redirect, abort
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
from core.database.repositories.poll_repository import PollRepository, POLL_OPEN

from core.decorators.user_decorators import update_last_seen, logout_barred_user, login_required, rw_required


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Remove vote
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/unvote', methods=['GET'])
@logout_barred_user
@update_last_seen
@login_required
@rw_required
def remove_vote():
    # ----------------------------------------------------------- #
    # Get params
    # ----------------------------------------------------------- #
    poll_id = request.args.get('poll_id', None)
    option = request.args.get('option', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not poll_id:
        app.logger.debug(f"remove_vote(): Missing poll_id!")
        EventRepository().log_event("remove_vote() Fail", f"Missing poll_id!")
        return abort(404)
    if not option or not option.isdigit():
        app.logger.debug(f"remove_vote(): Missing option!")
        EventRepository().log_event("remove_vote() Fail", f"Missing option!")
        return abort(404)
    option = int(option)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    poll = PollRepository().one_poll_by_id(poll_id)
    if not poll:
        app.logger.debug(f"remove_vote(): Failed to locate Poll with poll_id = '{poll_id}'.")
        EventRepository().log_event("remove_vote() Fail", f"Failed to locate Poll with poll_id = '{poll_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check permissions
    # ----------------------------------------------------------- #
    # Poll must be open
    if poll.status != POLL_OPEN:
        app.logger.debug(f"remove_vote(): Poll is closed, poll_id = '{poll_id}'.")
        EventRepository().log_event("remove_vote() Fail", f"Poll is closed, poll_id = '{poll_id}'.")
        flash("The poll is now closed!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Check poll options
    # ----------------------------------------------------------- #
    # Get poll options as a list
    option_list = json.loads(poll.options)
    # Get votes as a dictionary
    votes = json.loads(poll.responses)

    # Check option is a valid index into option_list (offset by 1 as option starts at 1)
    if option <= 0 or option > len(option_list):
        app.logger.debug(f"remove_vote(): Invalid option = '{option}'.")
        EventRepository().log_event("remove_vote() Fail", f"Invalid option = '{option}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check they have a vote to remove
    # ----------------------------------------------------------- #
    selected_option = option_list[option - 1]

    # Get votes for this selected_option
    try:
        option_votes = votes[selected_option]
    except KeyError:
        option_votes = []

    # Their email should be in the list
    if not current_user.email in option_votes:
        # Should never happen, but...
        app.logger.debug(f"remove_vote(): Can't remove non existent vote!")
        EventRepository().log_event("remove_vote() Fail", f"Can't remove non existent vote!")
        flash("Invalid vote option!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Remove their email
    # ----------------------------------------------------------- #
    # Remove email
    votes[selected_option].remove(current_user.email)
    # Push back to poll object as JSON string
    poll.responses = json.dumps(votes)
    # Update in db
    poll = PollRepository().add_poll(poll)
    # Did that work?
    if not poll:
        # Should never happen, but...
        app.logger.debug(f"remove_vote(): Can't update poll, id = '{poll_id}'!")
        EventRepository().log_event("remove_vote() Fail", f"Can't update poll, id = '{poll_id}'!")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Back to poll page
    # ----------------------------------------------------------- #

    return redirect(url_for(f'poll_details', poll_id=poll_id, anchor='votes'))


# -------------------------------------------------------------------------------------------------------------- #
# Add vote
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/vote', methods=['GET'])
@logout_barred_user
@update_last_seen
@login_required
@rw_required
def add_vote():
    # ----------------------------------------------------------- #
    # Get params
    # ----------------------------------------------------------- #
    poll_id = request.args.get('poll_id', None)
    option = request.args.get('option', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not poll_id:
        app.logger.debug(f"add_vote(): Missing poll_id!")
        EventRepository().log_event("add_vote() Fail", f"Missing poll_id!")
        return abort(404)
    if not option or not option.isdigit():
        app.logger.debug(f"add_vote(): Missing option!")
        EventRepository().log_event("add_vote() Fail", f"Missing option!")
        return abort(404)
    option = int(option)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    poll = PollRepository().one_poll_by_id(poll_id)
    if not poll:
        app.logger.debug(f"add_vote(): Failed to locate Poll with poll_id = '{poll_id}'.")
        EventRepository().log_event("add_vote() Fail", f"Failed to locate Poll with poll_id = '{poll_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check permissions
    # ----------------------------------------------------------- #
    # Poll must be open
    if poll.status != POLL_OPEN:
        app.logger.debug(f"add_vote(): Poll is closed, poll_id = '{poll_id}'.")
        EventRepository().log_event("add_vote() Fail", f"Poll is closed, poll_id = '{poll_id}'.")
        flash("The poll is now closed!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Check options
    # ----------------------------------------------------------- #
    # Get poll options as a list
    option_list = json.loads(poll.options)
    # Get votes as a dictionary
    if poll.responses:
        votes = json.loads(poll.responses)
    else:
        votes = {}

    # Check option is a valid index into option_list (offset by 1 as option starts at 1)
    if option <= 0 or option > len(option_list):
        app.logger.debug(f"add_vote(): Invalid option = '{option}'.")
        EventRepository().log_event("add_vote() Fail", f"Invalid option = '{option}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check they haven't already voted for this option
    # ----------------------------------------------------------- #
    selected_option = option_list[option - 1]

    # Get votes for this selected_option
    try:
        option_votes = votes[selected_option]
    except KeyError:
        votes[selected_option] = []
        option_votes = []

    # Their email should be in the list
    if current_user.email in option_votes:
        # Should never happen, but...
        app.logger.debug(f"remove_vote(): User already voted for this option!")
        EventRepository().log_event("remove_vote() Fail", f"User already voted for this optione!")
        flash("You've already voted for that option!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Add their email
    # ----------------------------------------------------------- #
    # Add email
    votes[selected_option].append(current_user.email)
    # Push back to poll object as JSON string
    poll.responses = json.dumps(votes)
    # Update in db
    poll = PollRepository().add_poll(poll)
    # Did that work?
    if not poll:
        # Should never happen, but...
        app.logger.debug(f"add_vote(): Can't update poll, id = '{poll_id}'!")
        EventRepository().log_event("add_vote() Fail", f"Can't update poll, id = '{poll_id}'!")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Back to poll page
    # ----------------------------------------------------------- #

    return redirect(url_for(f'poll_details', poll_id=poll_id, anchor='votes'))


# -------------------------------------------------------------------------------------------------------------- #
# Swap vote (if simple pick one poll, we can just remove existing vote and move it)
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/swapvote', methods=['GET'])
@logout_barred_user
@update_last_seen
@login_required
@rw_required
def swap_vote():
    # ----------------------------------------------------------- #
    # Get params
    # ----------------------------------------------------------- #
    poll_id = request.args.get('poll_id', None)
    option = request.args.get('option', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not poll_id:
        app.logger.debug(f"swap_vote(): Missing poll_id!")
        EventRepository().log_event("swap_vote() Fail", f"Missing poll_id!")
        return abort(404)
    if not option or not option.isdigit():
        app.logger.debug(f"swap_vote(): Missing option!")
        EventRepository().log_event("swap_vote() Fail", f"Missing option!")
        return abort(404)
    option = int(option)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    poll = PollRepository().one_poll_by_id(poll_id)
    if not poll:
        app.logger.debug(f"swap_vote(): Failed to locate Poll with poll_id = '{poll_id}'.")
        EventRepository().log_event("swap_vote() Fail", f"Failed to locate Poll with poll_id = '{poll_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check permissions
    # ----------------------------------------------------------- #
    # Poll must be open
    if poll.status != POLL_OPEN:
        app.logger.debug(f"swap_vote(): Poll is closed, poll_id = '{poll_id}'.")
        EventRepository().log_event("swap_vote() Fail", f"Poll is closed, poll_id = '{poll_id}'.")
        flash("The poll is now closed!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Extract options from JSON in db
    # ----------------------------------------------------------- #
    # option_list will look like ['Option 1', 'Option 2', 'Option 3']
    option_list = json.loads(poll.options)

    # ----------------------------------------------------------- #
    # Check their vote choice exists
    # ----------------------------------------------------------- #
    # Check option is a valid index into option_list (offset by 1 as option starts at 1)
    if option <= 0 or option > len(option_list):
        app.logger.debug(f"swap_vote(): Invalid option = '{option}'.")
        EventRepository().log_event("swap_vote() Fail", f"Invalid option = '{option}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Extract votes from JSON in db
    # ----------------------------------------------------------- #
    # votes looks like this: {
    #                          'Option 1': [Email1, Email2],
    #                          'Option 2': [Email3, Email4],
    #                          'Option 3': [Email 5]
    #                        }
    if poll.responses:
        votes = json.loads(poll.responses)
    else:
        # No one has voted yet, so empty dictionary
        votes = {}

    # ----------------------------------------------------------- #
    # Remove all existing votes
    # ----------------------------------------------------------- #
    for key, value in votes.items():
        if current_user.email in value:
            value.remove(current_user.email)

    # ----------------------------------------------------------- #
    # Add their email to their chosen option
    # ----------------------------------------------------------- #
    selected_option = option_list[option - 1]

    # Get votes for this selected_option
    try:
        option_votes = votes[selected_option]
    except KeyError:
        votes[selected_option] = []
        option_votes = []

    # Add email
    votes[selected_option].append(current_user.email)

    # ----------------------------------------------------------- #
    # Push results back to db
    # ----------------------------------------------------------- #
    # Convert to JSON string
    poll.responses = json.dumps(votes)
    # Update in db
    poll = PollRepository().add_poll(poll)
    # Did that work?
    if not poll:
        # Should never happen, but...
        app.logger.debug(f"swap_vote(): Can't update poll, id = '{poll_id}'!")
        EventRepository().log_event("swap_vote() Fail", f"Can't update poll, id = '{poll_id}'!")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Back to poll page
    # ----------------------------------------------------------- #
    return redirect(url_for(f'poll_details', poll_id=poll_id, anchor='votes'))

