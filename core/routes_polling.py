from flask import render_template, url_for, request, flash, redirect, abort
from flask_login import login_required, current_user
from werkzeug import exceptions
from datetime import datetime
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, update_last_seen, logout_barred_user
from core.dB_events import Event
from core.db_polls import Polls, create_poll_form, POLL_NO_RESPONSE, POLL_OPEN, POLL_CLOSED


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Filter polling options from html in for to list
# -------------------------------------------------------------------------------------------------------------- #

def extract_options_from_form(options):
    results = []

    chunks = options.split("<li>")
    for item in chunks:
        if "</li>" in item:
            results.append(item.split("</li>")[0])

    return results


# -------------------------------------------------------------------------------------------------------------- #
# Convert string in db into html
# -------------------------------------------------------------------------------------------------------------- #
def html_options(options: str):
    # Get set from the string the db
    data = json.loads(options)
    html = ""
    for item in data:
        html = html + "<li>" + item + "</li>"
    return html


# -------------------------------------------------------------------------------------------------------------- #
# Test for value in list for jinja
# -------------------------------------------------------------------------------------------------------------- #
def is_in_list(value, list):
    if value in list:
        return True
    return False

# Add to jinja
app.jinja_env.globals.update(is_in_list=is_in_list)


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# List all polls
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/polls', methods=['GET'])
@logout_barred_user
@update_last_seen
def poll_list():
    # ----------------------------------------------------------- #
    # Grab all the polls
    # ----------------------------------------------------------- #
    polls = Polls().all()

    # ----------------------------------------------------------- #
    #   Check polls haven't timed out
    # ----------------------------------------------------------- #
    for poll in polls:
        # Check each one
        if poll.status == POLL_OPEN:
            # Check date
            today_date = datetime.today().date()
            poll_date = datetime(int(poll.termination_date[4:8]),
                                 int(poll.termination_date[2:4]),
                                 int(poll.termination_date[0:2])).date()
            if poll_date < today_date:
                poll.status = POLL_CLOSED
                # Update poll
                Polls().add_poll(poll)

    # ----------------------------------------------------------- #
    #   Messages
    # ----------------------------------------------------------- #

    if not current_user.is_authenticated:
        flash("You will need to log in to participate in any polls.")
    elif not current_user.readwrite():
        flash("Currently you don't have permission to participate in any polls.")
        flash("Please contact an Admin via your user page.")

    # ----------------------------------------------------------- #
    #   Render page
    # ----------------------------------------------------------- #
    return render_template("poll_list.html", year=current_year, live_site=live_site(), polls=polls)


# -------------------------------------------------------------------------------------------------------------- #
# View a single poll
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/poll/<poll_id>', methods=['GET'])
@logout_barred_user
@update_last_seen
def poll_details(poll_id):
    # ----------------------------------------------------------- #
    # Did we get passed an anchor?
    # ----------------------------------------------------------- #
    anchor = request.args.get('anchor', None)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    poll = Polls().one_poll_by_id(poll_id)
    if not poll:
        app.logger.debug(f"poll_details(): Failed to locate Poll with poll_id = '{poll_id}'.")
        Event().log_event("One Poll Fail", f"Failed to locate Poll with poll_id = '{poll_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    #   Check poll hasn't timed out
    # ----------------------------------------------------------- #
    if poll.status == POLL_OPEN:
        # Check date
        today_date = datetime.today().date()
        poll_date = datetime(int(poll.termination_date[4:8]),
                             int(poll.termination_date[2:4]),
                             int(poll.termination_date[0:2])).date()
        if poll_date < today_date:
            flash("The poll has now closed")
            poll.status = POLL_CLOSED
            # Update poll
            Polls().add_poll(poll)

    # ----------------------------------------------------------- #
    #   Render page
    # ----------------------------------------------------------- #

    # Need options for form as a list
    poll.options_html = []
    for option in json.loads(poll.options):
        poll.options_html.append(option)

    # Need responses as a dictionary
    if poll.responses:
        poll.responses = json.loads(poll.responses)
    else:
        poll.responses = {}

    # ----------------------------------------------------------- #
    #   Number remaining votes
    # ----------------------------------------------------------- #
    num_votes = 0
    if poll.status == POLL_CLOSED:
        flash("This poll has now finished.")
    elif not current_user.is_authenticated:
        flash("You will need to log in to participate in any polls.")
    elif not current_user.readwrite():
        flash("Currently, you don't have permission to participate in polls.")
        flash("Please contact an Admin via your user page.")
    else:
        print(f"poll.responses = '{poll.responses}'")
        if current_user.is_authenticated:
            for option in json.loads(poll.options):
                print(f"option = '{option}'")
                try:
                    if current_user.email in poll.responses[option]:
                        num_votes += 1
                except KeyError:
                    pass

    return render_template("poll_details.html", year=current_year, live_site=live_site(), poll=poll,
                           num_votes=num_votes, anchor=anchor, POLL_OPEN=POLL_OPEN)


# -------------------------------------------------------------------------------------------------------------- #
# Create a new poll / edit an existing poll
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/add_poll', methods=['GET', 'POST'])
@logout_barred_user
@update_last_seen
@login_required
def add_poll():
    # ----------------------------------------------------------- #
    # Get poll_id from form (if one was posted)
    # ----------------------------------------------------------- #
    if request.method == 'POST':
        poll_id = request.form['poll_id']
    else:
        poll_id = None

    # ----------------------------------------------------------- #
    # Need a form
    # ----------------------------------------------------------- #
    form = create_poll_form(True)

    # ----------------------------------------------------------- #
    # Get poll from db
    # ----------------------------------------------------------- #
    if poll_id:
        # Look up the poll
        poll = Polls().one_poll_by_id(poll_id)

        if not poll:
            # Poll no longer / never existed
            app.logger.debug(f"add_poll(): Failed to find Poll, id = '{poll_id}'!")
            Event().log_event("add_poll Fail", f"Failed to find Poll, id = '{poll_id}'!")
            flash(f"That poll id '{poll_id}' doesn't seem to exist!")
            abort(404)

        # Not allowed to edit a poll in progress
        if poll.responses != POLL_NO_RESPONSE:
            app.logger.debug(f"add_poll(): Denied attempt to edit active poll, id = '{poll_id}'!")
            Event().log_event("add_poll Fail", f"Denied attempt to edit active poll, id = '{poll_id}'!")
            flash("You can't edit a poll once people have voted!")
            abort(403)

    else:
        # New poll
        poll = None

    # ----------------------------------------------------------- #
    # Get user
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(current_user.id)
    if not user:
        # Should never get here, but...
        app.logger.debug(f"add_poll(): Failed to find user, id = '{current_user.id}'!")
        Event().log_event("add_poll Fail", f"Failed to find user, id = '{current_user.id}'!")
        flash("The current user doesn't seem to exist!")
        abort(404)

    # ----------------------------------------------------------- #
    # Check read write
    # ----------------------------------------------------------- #
    if not user.readwrite():
        app.logger.debug(f"add_poll(): User doesn't have readwrite!")
        Event().log_event("add_poll Fail", f"User doesn't have readwrite!")
        flash("You don't have permission to create polls!")
        abort(403)

    # ----------------------------------------------------------- #
    # Manage form
    # ----------------------------------------------------------- #
    if request.method == 'GET':
        # ----------------------------------------------------------- #
        #   GET - Fill form in from dB
        # ----------------------------------------------------------- #
        if not poll_id:
            # Default value
            form.options.data = "<ul><li>Option 1</li><li>Option 2</li><li>Option 3</li></ul>"
            form.max_selections.data = 1
            form.poll_id.data = None
        else:
            # Populate form from db
            form.name.data = poll.name
            form.options.data = html_options(poll.options)
            form.details.data = poll.details
            form.privacy.data = poll.privacy
            form.max_selections.data = poll.max_selections
            form.poll_id.data = poll.id

    # Are we posting the completed form?
    if form.validate_on_submit():
        # ----------------------------------------------------------- #
        #   POST - form validated & submitted
        # ----------------------------------------------------------- #

        # Detect cancel
        if form.cancel.data:
            # Back to list of polls
            return redirect(url_for('poll_list'))

        # Save form details in the db
        if not poll:
            # Creating a new poll, so define these now
            poll = Polls()
            poll.created_date = datetime.today().date().strftime("%d%m%Y")
            poll.email = user.email
            poll.responses = POLL_NO_RESPONSE

        # Get these from the form
        poll.name = form.name.data
        poll.details = form.details.data
        poll.max_selections = form.max_selections.data
        poll.termination_date = form.termination_date.data.strftime("%d%m%Y")
        poll.status = form.status.data

        # Options need to be filtered
        poll.options = json.dumps(extract_options_from_form(form.options.data))

        # Add to db
        poll = Polls().add_poll(poll)
        if poll:
            # Success
            app.logger.debug(f"add_poll(): Successfully added new poll.")
            Event().log_event("Add Poll Pass", f"Successfully added new poll.")

        else:
            # Should never happen, but...
            app.logger.debug(f"add_poll(): Failed to add poll for '{poll}'.")
            Event().log_event("Add Poll Fail", f"Failed to add poll for '{poll}'.")
            flash("Sorry, something went wrong.")

        # They're finished
        if form.submit.data:
            # Back to list of polls
            flash("Poll has been published!")
            return redirect(url_for('poll_list'))
        else:
            # They're still editing
            flash("Please verify that the poll looks ok!")

    elif request.method == 'POST':

        # ----------------------------------------------------------- #
        #   POST - form validation failed
        # ----------------------------------------------------------- #

        # Detect user cancel
        if form.cancel.data:
            # Back to list of polls
            return redirect(url_for('poll_list'))
        else:
            # Give them a hint
            flash("Form not filled in properly, see below!")

    # ----------------------------------------------------------- #
    #   Render page
    # ----------------------------------------------------------- #

    # Need options for form as a list
    if poll:
        poll.options_html = []
        for option in extract_options_from_form(form.options.data):
            poll.options_html.append(option)

    # Make sure form has poll.id set (if we are editing an existing poll)
    if poll:
        form.poll_id.data = poll.id

    return render_template("poll_new.html", year=current_year, live_site=live_site(), form=form, poll=poll)


# -------------------------------------------------------------------------------------------------------------- #
# Remove vote
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/unvote', methods=['GET'])
@logout_barred_user
@update_last_seen
@login_required
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
        Event().log_event("remove_vote() Fail", f"Missing poll_id!")
        return abort(404)
    if not option or not option.isdigit():
        app.logger.debug(f"remove_vote(): Missing option!")
        Event().log_event("remove_vote() Fail", f"Missing option!")
        return abort(404)
    option = int(option)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    poll = Polls().one_poll_by_id(poll_id)
    if not poll:
        app.logger.debug(f"remove_vote(): Failed to locate Poll with poll_id = '{poll_id}'.")
        Event().log_event("remove_vote() Fail", f"Failed to locate Poll with poll_id = '{poll_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check permissions
    # ----------------------------------------------------------- #
    # User must have write permission
    if not current_user.readwrite():
        app.logger.debug(f"remove_vote(): User not readwrite!")
        Event().log_event("remove_vote() Fail", f"User not readwrite!")
        flash("You don't have permission to vote!")
        return abort(403)

    # Poll must be open
    if poll.status != POLL_OPEN:
        app.logger.debug(f"remove_vote(): Poll is closed, poll_id = '{poll_id}'.")
        Event().log_event("remove_vote() Fail", f"Poll is closed, poll_id = '{poll_id}'.")
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
        Event().log_event("remove_vote() Fail", f"Invalid option = '{option}'.")
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
        Event().log_event("remove_vote() Fail", f"Can't remove non existent vote!")
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
    poll = Polls().add_poll(poll)
    # Did that work?
    if not poll:
        # Should never happen, but...
        app.logger.debug(f"remove_vote(): Can't update poll, id = '{poll_id}'!")
        Event().log_event("remove_vote() Fail", f"Can't update poll, id = '{poll_id}'!")
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
        Event().log_event("add_vote() Fail", f"Missing poll_id!")
        return abort(404)
    if not option or not option.isdigit():
        app.logger.debug(f"add_vote(): Missing option!")
        Event().log_event("add_vote() Fail", f"Missing option!")
        return abort(404)
    option = int(option)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    poll = Polls().one_poll_by_id(poll_id)
    if not poll:
        app.logger.debug(f"add_vote(): Failed to locate Poll with poll_id = '{poll_id}'.")
        Event().log_event("add_vote() Fail", f"Failed to locate Poll with poll_id = '{poll_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check permissions
    # ----------------------------------------------------------- #
    # User must have write permission
    if not current_user.readwrite():
        app.logger.debug(f"add_vote(): User not readwrite!")
        Event().log_event("add_vote() Fail", f"User not readwrite!")
        flash("You don't have permission to vote!")
        return abort(403)

    # Poll must be open
    if poll.status != POLL_OPEN:
        app.logger.debug(f"add_vote(): Poll is closed, poll_id = '{poll_id}'.")
        Event().log_event("add_vote() Fail", f"Poll is closed, poll_id = '{poll_id}'.")
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
        Event().log_event("add_vote() Fail", f"Invalid option = '{option}'.")
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
        Event().log_event("remove_vote() Fail", f"User already voted for this optione!")
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
    poll = Polls().add_poll(poll)
    # Did that work?
    if not poll:
        # Should never happen, but...
        app.logger.debug(f"add_vote(): Can't update poll, id = '{poll_id}'!")
        Event().log_event("add_vote() Fail", f"Can't update poll, id = '{poll_id}'!")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Back to poll page
    # ----------------------------------------------------------- #

    return redirect(url_for(f'poll_details', poll_id=poll_id, anchor='votes'))


# -------------------------------------------------------------------------------------------------------------- #
# Delete poll
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/delete_poll', methods=['POST'])
@logout_barred_user
@update_last_seen
@login_required
def delete_poll():
    # ----------------------------------------------------------- #
    # Did we get passed a poll_id?
    # ----------------------------------------------------------- #
    poll_id = request.args.get('poll_id', None)
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
    # Must have parameters
    # ----------------------------------------------------------- #
    if not poll_id:
        app.logger.debug(f"delete_poll(): Missing poll_id!")
        Event().log_event("Delete poll Fail", f"Missing poll_id!")
        return abort(400)
    if not password:
        app.logger.debug(f"delete_poll(): Missing Password!")
        Event().log_event("Delete poll Fail", f"Missing Password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate poll_id
    # ----------------------------------------------------------- #
    poll = Polls().one_poll_by_id(poll_id)
    if not poll:
        app.logger.debug(f"delete_poll(): Failed to locate poll, poll_id = '{poll_id}'.")
        Event().log_event("Delete poll Fail", f"Failed to locate poll, poll_id = '{poll_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Must be admin or the current author
    if current_user.email != poll.email \
            and not current_user.admin() or \
            not current_user.readwrite():
        # Failed authentication
        app.logger.debug(f"delete_poll(): Refusing permission for '{current_user.email}' and "
                         f"poll_id = '{poll_id}'.")
        Event().log_event("Delete poll Fail", f"Refusing permission for '{current_user.email}', "
                                                f"poll_id = '{poll_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    #  Validate password
    # ----------------------------------------------------------- #
    # Need current user
    user = User().find_user_from_id(current_user.id)

    # Validate against current_user's password
    if not user.validate_password(user, password, user_ip):
        app.logger.debug(f"delete_polll(): Delete failed, incorrect password for user_id = '{user.id}'!")
        Event().log_event("Poll Delete Fail", f"Incorrect password for user_id = '{user.id}'!")
        flash(f"Incorrect password for user {user.name}!")
        # Go back to polls page
        return redirect(url_for('poll_list'))

    # ----------------------------------------------------------- #
    # Delete Poll
    # ----------------------------------------------------------- #
    if Polls().delete_poll(poll_id):
        app.logger.debug(f"delete_poll(): Deleted poll, poll_id = '{poll_id}'.")
        Event().log_event("Delete poll Success", f"Deleted poll, poll_id = '{poll_id}'.")
        flash("Poll has been deleted.")
    else:
        app.logger.debug(f"delete_poll(): Failed to delete poll, poll_id = '{poll_id}''.")
        Event().log_event("Delete poll Fail", f"Failed to delete poll, poll_id = '{poll_id}'.")
        flash("Sorry, something went wrong.")

    # Back to list of all polls
    return redirect(url_for('poll_list'))


# -------------------------------------------------------------------------------------------------------------- #
# Swap vote (if simple pick one poll, we can just remove existing vote and move it)
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/swapvote', methods=['GET'])
@logout_barred_user
@update_last_seen
@login_required
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
        Event().log_event("swap_vote() Fail", f"Missing poll_id!")
        return abort(404)
    if not option or not option.isdigit():
        app.logger.debug(f"swap_vote(): Missing option!")
        Event().log_event("swap_vote() Fail", f"Missing option!")
        return abort(404)
    option = int(option)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    poll = Polls().one_poll_by_id(poll_id)
    if not poll:
        app.logger.debug(f"swap_vote(): Failed to locate Poll with poll_id = '{poll_id}'.")
        Event().log_event("swap_vote() Fail", f"Failed to locate Poll with poll_id = '{poll_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check permissions
    # ----------------------------------------------------------- #
    # User must have write permission
    if not current_user.readwrite():
        app.logger.debug(f"swap_vote(): User not readwrite!")
        Event().log_event("swap_vote() Fail", f"User not readwrite!")
        flash("You don't have permission to vote!")
        return abort(403)

    # Poll must be open
    if poll.status != POLL_OPEN:
        app.logger.debug(f"swap_vote(): Poll is closed, poll_id = '{poll_id}'.")
        Event().log_event("swap_vote() Fail", f"Poll is closed, poll_id = '{poll_id}'.")
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
        Event().log_event("swap_vote() Fail", f"Invalid option = '{option}'.")
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
    poll = Polls().add_poll(poll)
    # Did that work?
    if not poll:
        # Should never happen, but...
        app.logger.debug(f"swap_vote(): Can't update poll, id = '{poll_id}'!")
        Event().log_event("swap_vote() Fail", f"Can't update poll, id = '{poll_id}'!")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Back to poll page
    # ----------------------------------------------------------- #
    return redirect(url_for(f'poll_details', poll_id=poll_id, anchor='votes'))
