# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Routes and associated helper functions for managing Users
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

from flask import render_template, redirect, url_for, flash, request, abort, session, make_response
from flask_login import current_user, logout_user
from werkzeug import exceptions
from urllib.parse import urlparse
import os
import re
from datetime import datetime
import json
import validators


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site

# -------------------------------------------------------------------------------------------------------------- #
# Import our database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, update_last_seen, logout_barred_user, DELETED_NAME, ChangeUserDetailsForm, \
                          NOTIFICATIONS_DEFAULT_VALUE, login_required, rw_required
from core.dB_cafes import Cafe
from core.dB_gpx import Gpx
from core.dB_cafe_comments import CafeComment
from core.db_messages import Message, ADMIN_EMAIL
from core.dB_events import Event
from core.subs_google_maps import MAP_BOUNDS, google_maps_api_key, count_map_loads
from core.db_calendar import Calendar
from core.db_social import Socials
from core.database.repositories.blog_repository import BlogRepository as Blog
from core.db_classifieds import Classified


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

DEFAULT_EVENT_DAYS = 7

# This is the admin email address
admin_email_address = os.environ['ELSR_ADMIN_EMAIL']
admin_phone_number = os.environ['ELSR_TWILIO_NUMBER']


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def same_origin(current_uri, compare_uri):
    current = urlparse(current_uri)
    compare = urlparse(compare_uri)

    return (
            current.scheme == compare.scheme
            and current.hostname == compare.hostname
            and current.port == compare.port
    )


def validate_phone_number(phone_number):
    # ----------------------------------------------------------- #
    # Check phone number
    # ----------------------------------------------------------- #
    # Strip all spaces
    phone_number = phone_number.strip().replace(" ", "")
    print(f"'{phone_number}', '{phone_number[0:2]}'")

    # Check for UK code
    if phone_number[0:3] != "+44":
        flash("Phone number must start with '+44'!")
        return None

    # Strip any non digits (inc leading '+')
    phone_number = re.sub('[^0-9]', '', phone_number)
    if len(phone_number) != 12:
        flash("Phone number must be 12 digis long eg '+44 1234 123456'!")
        return None

    # Add back leading '+'
    phone_number = "+" + phone_number
    return phone_number


# -------------------------------------------------------------------------------------------------------------- #
# Process social links
# -------------------------------------------------------------------------------------------------------------- #
def validate_socials(user, form):
    # ----------------------------------------------------------- #
    # Get new social links from the form
    # ----------------------------------------------------------- #
    new_strava = form.strava.data.strip()
    new_instagram = form.instagram.data.strip()
    new_twitter = form.twitter.data.strip()
    new_facebook = form.facebook.data.strip()
    new_group = form.group.data.strip()

    # ----------------------------------------------------------- #
    # Did anything change
    # ----------------------------------------------------------- #
    if new_strava == user.social_url("strava") and \
            new_instagram == user.social_url("instagram") and \
            new_twitter == user.social_url("twitter") and \
            new_facebook == user.social_url("facebook") and \
            new_group == user.social_url("group"):
        # Nothing changed
        return False

    # ----------------------------------------------------------- #
    # Validate URLs for social links
    # ----------------------------------------------------------- #
    if new_strava != "":
        if not validators.url(new_strava):
            flash("That's not a valid Strava link!")
            new_strava = user.social_url("strava")
    if new_instagram != "":
        if not validators.url(new_instagram):
            flash("That's not a valid Instagram link!")
            new_instagram = user.social_url("instagram")
    if new_twitter != "":
        if not validators.url(new_twitter):
            flash("That's not a valid Twitter link!")
            new_twitter = user.social_url("twitter")
    if new_facebook != "":
        if not validators.url(new_facebook):
            flash("That's not a valid Facebook link!")
            new_facebook = user.social_url("facebook")

    # ----------------------------------------------------------- #
    # Update user
    # ----------------------------------------------------------- #
    user.socials = json.dumps({'strava': new_strava,
                               'instagram': new_instagram,
                               'twitter': new_twitter,
                               'facebook': new_facebook,
                               'group': new_group})
    # Return True to update user
    return True


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# User home page
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/user_page', methods=['GET', 'POST'])
@login_required
@update_last_seen
def user_page():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)  # Mandatory
    event_period = request.args.get('days', None)  # Optional
    anchor = request.args.get('anchor', None)  # Optional

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"user_page(): Missing user_id!")
        Event().log_event("User Page Fail", f"Missing user_id!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"user_page(): Invalid user user_id = '{user_id}'!")
        Event().log_event("User Page Fail", f"Invalid user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    #  1. Admin can see any user's page
    #  2. A user can see their page
    #  3. Deleted users pages are denied
    if int(current_user.id) != int(user_id) and \
            not current_user.admin() or \
            user.name == DELETED_NAME:
        app.logger.debug(f"user_page(): Rejected request from current_user.id = '{current_user.id}', "
                         f"for user_id = '{user_id}'.")
        Event().log_event("User Page Fail", f"Rejected request from current_user.id = '{current_user.id}', "
                                            f"for user_id = '{user_id}'.")
        abort(403)

    # ----------------------------------------------------------- #
    # Gather data: 1. Events
    # ----------------------------------------------------------- #
    if not event_period:
        events = Event().all_events_email_days(user.email, DEFAULT_EVENT_DAYS)
        days = DEFAULT_EVENT_DAYS
    elif event_period == "all":
        events = Event().all_events_email(user.email)
        days = "all"
    else:
        events = Event().all_events_email_days(user.email, int(event_period))
        days = int(event_period)

    # ----------------------------------------------------------- #
    # Gather data: 2. Cafes
    # ----------------------------------------------------------- #
    cafes = Cafe().find_all_cafes_by_email(user.email)

    # ----------------------------------------------------------- #
    # Gather data: 3. GPX files
    # ----------------------------------------------------------- #
    gpxes = Gpx().all_gpxes_by_email(user.email)

    # ----------------------------------------------------------- #
    # Gather data: 4. Comments
    # ----------------------------------------------------------- #
    cafe_comments = CafeComment().all_comments_by_email(user.email)

    # ----------------------------------------------------------- #
    # Gather data: 5. Messages
    # ----------------------------------------------------------- #
    messages = Message().all_messages_to_email(user.email)

    # Any unread?
    count = 0
    for message in messages:
        if message.from_email == ADMIN_EMAIL:
            message.from_name = "Admin team"
        else:
            message.from_name = User().find_user_from_email(message.from_email).name
        if not message.been_read():
            count += 1

    if count > 0:
        if count == 1:
            flash(f"You have {count} unread message")
        else:
            flash(f"You have {count} unread messages")

    # ----------------------------------------------------------- #
    # Gather data: 6. Rides
    # ----------------------------------------------------------- #
    rides = Calendar().all_calendar_email(user.email)

    # ----------------------------------------------------------- #
    # Gather data: 7. Social events
    # ----------------------------------------------------------- #
    socials = Socials().all_by_email(user.email)

    # ----------------------------------------------------------- #
    # Gather data: 8. Classifieds
    # ----------------------------------------------------------- #
    classifieds = Classified().all_by_email(user.email)

    # ----------------------------------------------------------- #
    # Gather data: 9. Notification preferences
    # ----------------------------------------------------------- #
    notifications = user.notification_choices_set()

    # ----------------------------------------------------------- #
    # Gather data: 10. Blog posts
    # ----------------------------------------------------------- #
    blogs = Blog().all_by_email(user.email)
    for blog in blogs:

        # 1. Human-readable date
        if blog.date_unix:
            blog.date = datetime.utcfromtimestamp(blog.date_unix).strftime('%d %b %Y')

    # ----------------------------------------------------------- #
    # ----------------------------------------------------------- #
    # Manage form on page
    # ----------------------------------------------------------- #
    # ----------------------------------------------------------- #
    form = ChangeUserDetailsForm()

    if request.method == 'GET':
        # ----------------------------------------------------------- #
        # Fill in blank form before displaying
        # ----------------------------------------------------------- #
        form.name.data = user.name
        form.bio.data = user.bio
        form.group.data = user.social_url("group")
        form.strava.data = user.social_url("strava")
        form.instagram.data = user.social_url("instagram")
        form.twitter.data = user.social_url("twitter")
        form.facebook.data = user.social_url("facebook")
        form.emergency.data = user.emergency_contacts

    elif form.validate_on_submit():
        # ----------------------------------------------------------- #
        # Process submitted form
        # ----------------------------------------------------------- #

        # Read the form
        made_change = False
        new_name = form.name.data.strip()
        new_bio = form.bio.data
        new_emergency = form.emergency.data

        # Did they change their username?
        if new_name != user.name:
            # Needs to be unique
            if User().check_name_in_use(new_name):
                # Not unique
                flash(f"Sorry, the name '{new_name}' is already in use!")
                app.logger.debug(f"user_page(): Username clash '{new_name}' for user_id = '{user_id}'.")
                Event().log_event("User Page Success", f"Username clash '{new_name}' for user_id = '{user_id}'.")
            else:
                # Change their name
                user.name = new_name
                made_change = True

        # Did they change their bio?
        if new_bio != user.bio:
            # Update it
            user.bio = new_bio
            made_change = True

        # Handle socials
        if validate_socials(user, form):
            made_change = True

        # Emergency Contact Details
        if new_emergency != user.emergency_contacts:
            # Update it
            user.emergency_contacts = new_emergency
            made_change = True

        # Update user object
        if made_change:
            if User().update_user(user):
                app.logger.debug(f"user_page(): Updated user, user_id = '{user_id}'.")
                Event().log_event("User Page Success", f"Updated user, user_id = '{user_id}'.")
                flash("User has been updated!")
                return redirect(url_for('user_page', user_id=user_id, anchor="account"))
            else:
                # Should never get here, but..
                app.logger.debug(f"user_page(): Failed to update user, user_id = '{user_id}'.")
                Event().log_event("User Page Fail", f"Failed to update user, user_id = '{user_id}'.")
                flash("Sorry, something went wrong!")
                return redirect(url_for('user_page', user_id=user_id, anchor="account"))
        else:
            # They didn't change anything
            flash("Nothing was changed!")
            return redirect(url_for('user_page', user_id=user_id, anchor="account"))

    elif request.method == 'POST':
        # ----------------------------------------------------------- #
        # Failed form validation
        # ----------------------------------------------------------- #
        flash("Check form for errors!")

    # -------------------------------------------------------------------------------------------- #
    # Show user page
    # -------------------------------------------------------------------------------------------- #

    # Keep count of Google Map Loads
    count_map_loads(1)

    # Add an anchor tag if the Admin is changing the Event view settings
    if event_period:
        anchor = "eventLog"

    return render_template("user_page.html", year=current_year, cafes=cafes, user=user, gpxes=gpxes,
                           cafe_comments=cafe_comments, messages=messages, events=events, days=days,
                           rides=rides, socials=socials, notifications=notifications, blogs=blogs,
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS, form=form,
                           classifieds=classifieds, live_site=live_site(), anchor=anchor)


# -------------------------------------------------------------------------------------------------------------- #
# Delete user - user can delete themselves so *NOT* restricted to Admin only
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


# -------------------------------------------------------------------------------------------------------------- #
# Update notification settings
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/set_notifications', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def set_notifications():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    choices = request.args.get('choices', None)
    try:
        user_id = request.form['user_id']
    except exceptions.BadRequestKeyError:
        user_id = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"set_notifications(): Missing user_id!")
        Event().log_event("Set Notifications Fail", f"missing user id")
        abort(400)
    elif not choices:
        app.logger.debug(f"set_notifications(): Missing choices!")
        Event().log_event("Set Notifications Fail", f"Missing choices")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"set_notifications(): Invalid user user_id = '{user_id}'!")
        Event().log_event("Set Notifications Fail", f"Invalid user user_id = '{user_id}'!")
        abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if int(current_user.id) != int(user_id) and \
            not current_user.admin():
        app.logger.debug(f"set_notifications(): User isn't allowed "
                         f"current_user.id='{current_user.id}', user_id='{user_id}'.")
        Event().log_event("Set Notifications Fail", f"User isn't allowed "
                                                    f"current_user.id='{current_user.id}', user_id='{user_id}'.")
        abort(403)

    # ----------------------------------------------------------- #
    # Update notification preferences
    # ----------------------------------------------------------- #
    if User().set_notifications(user_id, choices):
        app.logger.debug(f"set_notifications(): Success, user '{user.email}' has set notifications = '{choices}'.")
        Event().log_event("Set Notifications Success", f"User '{user.email}' has set notifications = '{choices}'.")
        flash("Notifications have been updated!")
    else:
        # Should never get here, but...
        app.logger.debug(f"dset_notifications():  user.set_notifications failed for user_id = '{user_id}'.")
        Event().log_event("Set Notifications Fail", f" user.set_notifications failed for user_id = '{user_id}'.")
        flash("Sorry, something went wrong.")

    # Back to user page
    return redirect(url_for('user_page', anchor="notifications", user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Update notification settings
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/unsubscribe_all', methods=['GET'])
@logout_barred_user
@update_last_seen
def unsubscribe_all():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    email = request.args.get('email', None)
    code = request.args.get('code', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not email:
        app.logger.debug(f"unsubscribe_all(): Missing email!")
        Event().log_event("unsubscribe_all Fail", f"missing email!")
        abort(400)
    elif not code:
        app.logger.debug(f"unsubscribe_all(): Missing code!")
        Event().log_event("unsubscribe_all Fail", f"Missing code!")
        abort(400)

    # ----------------------------------------------------------- #
    # Validate parameters
    # ----------------------------------------------------------- #
    user = User().find_user_from_email(email)
    if not user:
        app.logger.debug(f"unsubscribe_all(): Invalid email = '{email}'!")
        Event().log_event("unsubscribe_all Fail", f"Invalid email = '{email}'!")
        abort(404)
    if code != user.unsubscribe_code():
        app.logger.debug(f"unsubscribe_all(): Invalid code = '{code}' for user '{user.email}'!")
        Event().log_event("unsubscribe_all Fail", f"Invalid code = '{code}' for user '{user.email}'!")
        abort(404)

    # ----------------------------------------------------------- #
    # Success
    # ----------------------------------------------------------- #
    flash("You have been unsubscribed from all email notifications EXCEPT classifieds!")
    flash("You must delete any classifieds to prevent emails from buyers.")
    app.logger.debug(f"unsubscribe_all(): Successfully unsubscribed user '{user.email}'!")
    Event().log_event("unsubscribe_all Fail", f"Successfully unsubscribed user '{user.email}'!")
    User().set_notifications(user.id, NOTIFICATIONS_DEFAULT_VALUE)

    # ----------------------------------------------------------- #
    # Return page
    # ----------------------------------------------------------- #
    # Are they logged in?
    if current_user.is_authenticated:
        # Better check this so as not to forward to a user page they don't have permission to see
        if current_user.id == user.id:
            # Back to their user page
            return redirect(url_for('user_page', user_id=user.id))

    # Revert to home page
    return redirect(url_for('home'))


# -------------------------------------------------------------------------------------------------------------- #
# Show user list
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/who_are_we', methods=['GET'])
@logout_barred_user
@update_last_seen
def who_are_we():
    return render_template("under_construction.html", year=current_year, live_site=live_site())

    # ----------------------------------------------------------- #
    # Need a list of users
    # ----------------------------------------------------------- #
    users = User().all_users_sorted()

    # ----------------------------------------------------------- #
    # Need a list of letters
    # ----------------------------------------------------------- #
    username_letters = []

    for user in users:
        username_letter = user.name[0].upper()
        if not username_letter in username_letters:
            username_letters.append(username_letter)

    # Render in main index template
    return render_template("user_list.html", year=current_year, users=users, username_letters=username_letters,
                           live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Show Emergency Contacts
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/emergency', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def emergency():
    # ----------------------------------------------------------- #
    # Validate user
    # ----------------------------------------------------------- #
    if not current_user.can_see_emergency_contacts():
        # Naughty boy
        app.logger.debug(f"emergency(): Non Admin access, user_id = '{current_user.id}'!")
        Event().log_event("Admin Page Fail", f"on emergency access, user_id = '{current_user.id}'!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Need a list of users
    # ----------------------------------------------------------- #
    users = User().all_users_sorted()

    # ----------------------------------------------------------- #
    # Need a list of letters
    # ----------------------------------------------------------- #
    username_letters = []

    for user in users:
        username_letter = user.name[0].upper()
        if not username_letter in username_letters:
            username_letters.append(username_letter)

    # Render in main index template
    return render_template("emergency.html", year=current_year, users=users, username_letters=username_letters,
                           live_site=live_site())
