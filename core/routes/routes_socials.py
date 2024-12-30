from flask import render_template, url_for, request, flash, redirect, abort, send_from_directory
from flask_login import current_user
from werkzeug import exceptions
from datetime import datetime
from ics import Calendar as icsCalendar, Event as icsEvent
import os
from threading import Thread
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site, ICS_DIRECTORY


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.social_repository import SocialRepository, SOCIAL_FORM_PRIVATE, SOCIAL_DB_PRIVATE, \
                                                 SOCIAL_FORM_PUBLIC, SOCIAL_DB_PUBLIC, SIGN_UP_YES, SIGN_UP_NO
from core.forms.social_forms import create_social_form
from core.database.repositories.event_repository import EventRepository
from core.database.repositories.user_repository import UserRepository
from core.subs_email_sms import send_social_notification_emails
from core.subs_dates import get_date_from_url

from core.decorators.user_decorators import update_last_seen, logout_barred_user, login_required, rw_required


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Add a social event
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/add_social', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def route_add_social():
    # ----------------------------------------------------------- #
    # Did we get passed a social_id? (Optional)
    # ----------------------------------------------------------- #
    social_id = request.args.get('social_id', None)

    # ----------------------------------------------------------- #
    # Validate social_id
    # ----------------------------------------------------------- #
    if social_id:
        social = SocialRepository().one_social_id(social_id)
        if not social:
            app.logger.debug(f"add_social(): Failed to locate social, social_id = '{social_id}'.")
            EventRepository().log_event("Add Social Fail", f"Failed to locate social, social_id = '{social_id}'.")
            return abort(404)
    else:
        social = None

    # ----------------------------------------------------------- #
    # Need a form
    # ----------------------------------------------------------- #
    form = create_social_form(current_user.admin)

    if request.method == 'GET':
        if social:
            # Try and get owner from email address in the db
            owner = UserRepository().find_user_from_email(social.email)
            if not owner:
                # Should never happen but....
                app.logger.debug(f"add_social(): Failed to locate owner, "
                                 f"social_id = '{social_id}', social.email = '{social.email}'.")
                EventRepository().log_event("Edit Social Fail", f"Failed to locate owner, "
                                                      f"social_id = '{social_id}', social.email = '{social.email}'.")
                flash("Failed to locate owner, so defaulting to current_user")
                # Default to current user
                owner = current_user

            # We are editing an existing event, so pre-fill details
            form.date.data = datetime.strptime(social.date.strip(), '%d%m%Y')
            form.start_time.data = datetime.strptime(f"{social.date} {social.start_time}", '%d%m%Y %H%M').time()
            form.organiser.data = social.organiser
            form.destination.data = social.destination
            form.details.data = social.details
            if social.privacy == SOCIAL_DB_PRIVATE:
                form.destination_hidden.data = SOCIAL_FORM_PRIVATE
            else:
                form.destination_hidden.data = SOCIAL_FORM_PUBLIC
            if social.sign_up == "True":
                form.sign_up.data = SIGN_UP_YES
            else:
                form.sign_up.data = SIGN_UP_NO

            # Admin owner option
            if current_user.admin:
                form.owner.data = owner.combo_str

        else:
            # New form, so just assume organiser is current user
            form.organiser.data = current_user.name
            if current_user.admin:
                form.owner.data = current_user.combo_str

            # Add some guidance
            form.details.data = "<p>If you set the Social type to <strong>Public</strong>:</p>" \
                                "<ul><li>Destination and Details are hidden for anyone not logged in.</li>" \
                                "<li>But, visible to anyone who has registered (ie anyone who can be bothered to give " \
                                "the site an email address).</li></ul>" \
                                "<p>However, the Admins maintain a subset of members (same as WA group) and only " \
                                "these people can see the Destination and Details of <strong>Private</strong> events. " \
                                "So, <strong>Public</strong> = social down the pub, but BBQ at your house should be " \
                                "made <strong>Private</strong>!</p>"

    elif form.validate_on_submit():
        # ----------------------------------------------------------- #
        # Handle form passing validation
        # ----------------------------------------------------------- #

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('calendar'))

        # ----------------------------------------------------------- #
        # We can now create / update the social object
        # ----------------------------------------------------------- #
        if social:
            # Updating an existing social
            new_social = social
        else:
            # New social
            new_social = SocialRepository()

        # Get owner
        if current_user.admin:
            owner = UserRepository().user_from_combo_string(form.owner.data)
            if not owner:
                # Should never happen but....
                app.logger.debug(f"add_social(): Failed to locate owner, "
                                 f"social_id = '{social_id}', social.email = '{social.email}'.")
                EventRepository().log_event("Edit Social Fail", f"Failed to locate owner, "
                                                      f"social_id = '{social_id}', social.email = '{social.email}'.")
                flash("Failed to locate owner, so defaulting to current_user")
                # Default to current user
                owner = current_user
        else:
            owner = current_user

        new_social.organiser = form.organiser.data
        new_social.email = owner.email
        # Convert form date format '2023-06-23' to preferred format '23062023'
        new_social.date = form.date.data.strftime("%d%m%Y")
        new_social.start_time = form.start_time.data.strftime("%H%M")
        new_social.destination = form.destination.data
        new_social.details = form.details.data
        # Handle public private
        if form.destination_hidden.data == SOCIAL_FORM_PUBLIC:
            new_social.privacy = SOCIAL_DB_PUBLIC
        else:
            new_social.privacy = SOCIAL_DB_PRIVATE
        # Handle sign ups
        if form.sign_up.data == SIGN_UP_YES:
            new_social.sign_up = "True"
        else:
            new_social.sign_up = "False"

        # ----------------------------------------------------------- #
        # Add to the db
        # ----------------------------------------------------------- #
        new_social = SocialRepository().add_social(new_social)
        if new_social:
            # Success
            app.logger.debug(f"add_social(): Successfully added new social.")
            EventRepository().log_event("Add social Pass", f"Successfully added new social.")
            if social:
                flash("Social updated!")
            else:
                flash("Social added to Calendar!")
                Thread(target=send_social_notification_emails, args=(new_social,)).start()
            # Back to socials page showing the new social
            return redirect(url_for('social', date=new_social.date))

        else:
            # Should never happen, but...
            app.logger.debug(f"add_social(): Failed to add social for '{new_social}'.")
            EventRepository().log_event("Add Social Fail", f"Failed to add social for '{new_social}'.")
            flash("Sorry, something went wrong.")
            return render_template("calendar_add_social.html", year=current_year, form=form, social=social,
                                   live_site=live_site())

    elif request.method == 'POST':
        # ----------------------------------------------------------- #
        # Handle form failing validation
        # ----------------------------------------------------------- #

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('calendar'))

        # This traps a post, but where the form verification failed.
        flash("Something was missing, see comments below:")
        return render_template("calendar_add_social.html", year=current_year, form=form, social=social,
                               live_site=live_site())

    return render_template("calendar_add_social.html", year=current_year, form=form, social=social,
                           live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Show all socials for a given date
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/social", methods=['GET'])
@logout_barred_user
@update_last_seen
def social():
    # ----------------------------------------------------------- #
    # Did we get passed a date? (optional)
    # ----------------------------------------------------------- #
    date = get_date_from_url(return_none_if_empty=True)
    anchor = request.args.get('anchor', None)

    # ----------------------------------------------------------- #
    # Get our socials
    # ----------------------------------------------------------- #
    if date:
        # Get socials specific to that date
        socials = SocialRepository().all_socials_date(date)

    else:
        # Just get ones yet to happen
        socials = SocialRepository().all_socials_future()

    # ----------------------------------------------------------- #
    # Tweak the data before we show it
    # ----------------------------------------------------------- #
    for social in socials:
        # Convert attendees from string to list
        if social.attendees:
            social.attendees = json.loads(social.attendees)
        else:
            social.attendees = []
        # Swap 'True' / 'False' in db for boolean for jinja
        social.sign_up = social.sign_up == "True"

        # Add more friendly start time
        if social.start_time:
            social.start_time_txt = f"{social.start_time[0:2]}:{social.start_time[2:4]}"
        else:
            social.start_time_txt = "TBC"

        # Hide destination for private events
        social.show_ics = False
        if not current_user.is_authenticated:
            # Not logged in = no info other than the date
            social.destination = "Log in to see destination"
            social.start_time_txt = "Log in to see start time"
            social.details = f"<a href={url_for('login')}><p style='color: red'>Log in to see the details</p></a>"

        elif social.privacy == SOCIAL_DB_PRIVATE and \
                not current_user.readwrite:
            # Private events are for write enabled users only ie WA group members
            social.destination = "** Private event **"
            social.details = "<p>Details for private events are visible to regular riders only.</p>"
            social.start_time_txt = "** Private event **"
        else:
            social.show_ics = True

    return render_template("main_social.html", year=current_year, socials=socials, date=date, live_site=live_site(),
                           anchor=anchor)


# -------------------------------------------------------------------------------------------------------------- #
# Add a social event
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/delete_social', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def delete_social():
    # ----------------------------------------------------------- #
    # Did we get passed a social_id?
    # ----------------------------------------------------------- #
    social_id = request.args.get('social_id', None)
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
    if not social_id:
        app.logger.debug(f"delete_social(): Missing social_id!")
        EventRepository().log_event("Delete social Fail", f"Missing social_id!")
        return abort(400)
    if not password:
        app.logger.debug(f"delete_social(): Missing Password!")
        EventRepository().log_event("Delete social Fail", f"Missing Password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate social_id
    # ----------------------------------------------------------- #
    social = SocialRepository().one_social_id(social_id)
    if not social:
        app.logger.debug(f"delete_social(): Failed to locate social, social_id = '{social_id}'.")
        EventRepository().log_event("Delete Social Fail", f"Failed to locate social, social_id = '{social_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access to Admin and Author
    # ----------------------------------------------------------- #
    # Must be admin or the current author
    if current_user.email != social.email \
            and not current_user.admin:
        # Failed authentication
        app.logger.debug(f"delete_social(): Refusing permission for '{current_user.email}' and "
                         f"social_id = '{social_id}'.")
        EventRepository().log_event("Delete Social Fail", f"Refusing permission for '{current_user.email}', "
                                                f"social_id = '{social_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    #  Validate password
    # ----------------------------------------------------------- #
    # Need current user
    user = UserRepository().find_user_from_id(current_user.id)

    # Validate against current_user's password
    if not user.validate_password(user, password, user_ip):
        app.logger.debug(f"delete_social(): Delete failed, incorrect password for user_id = '{user.id}'!")
        EventRepository().log_event("Social Delete Fail", f"Incorrect password for user_id = '{user.id}'!")
        flash(f"Incorrect password for user {user.name}!")
        # Go back to socials page
        return redirect(url_for('social'))

    # ----------------------------------------------------------- #
    # Delete social
    # ----------------------------------------------------------- #
    if SocialRepository().delete_social(social_id):
        app.logger.debug(f"delete_social(): Deleted social, social_id = '{social_id}'.")
        EventRepository().log_event("Delete Social Success", f"Deleted social, social_id = '{social_id}'.")
        flash("Social has been deleted.")
    else:
        app.logger.debug(f"delete_social(): Failed to delete social, social_id = '{social_id}'.")
        EventRepository().log_event("Delete Social Fail", f"Failed to delete social, social_id = '{social_id}'.")
        flash("Sorry, something went wrong.")

    return redirect(url_for('social'))


# -------------------------------------------------------------------------------------------------------------- #
# Download ics file
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/download_ics', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def download_ics():
    # ----------------------------------------------------------- #
    # Did we get passed a social_id?
    # ----------------------------------------------------------- #
    social_id = request.args.get('social_id', None)

    # ----------------------------------------------------------- #
    # Must have parameters
    # ----------------------------------------------------------- #
    if not social_id:
        app.logger.debug(f"download_ics(): Missing social_id!")
        EventRepository().log_event("download_ics Fail", f"Missing social_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate social_id
    # ----------------------------------------------------------- #
    social = SocialRepository().one_social_id(social_id)
    if not social:
        app.logger.debug(f"download_ics(): Failed to locate social, social_id = '{social_id}'.")
        EventRepository().log_event("download_ics Fail", f"Failed to locate social, social_id = '{social_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Permissions
    # ----------------------------------------------------------- #
    if not current_user.readwrite and \
            social.privacy == SOCIAL_DB_PRIVATE:
        # Failed authentication
        app.logger.debug(f"delete_social(): Refusing permission for '{current_user.email}' and "
                         f"social_id = '{social_id}' as Private.")
        EventRepository().log_event("Delete SocialX Fail", f"Refusing permission for '{current_user.email}', "
                                                 f"social_id = '{social_id}' as Private.")
        flash("Private events are for regular riders only!")
        return redirect(url_for("not_rw"))

    # ----------------------------------------------------------- #
    # Create ics file
    # ----------------------------------------------------------- #
    new_event = icsEvent()
    new_event.name = "ELSR Social"
    new_event.begin = f"{social.date[4:8]}-{social.date[2:4]}-{social.date[0:2]} " \
                      f"{social.start_time[0:2]}:{social.start_time[2:4]}:00"
    new_event.location = social.destination
    new_event.description = f"ELSR Social organised by {social.organiser}: {social.details} \n\n " \
                            f"https://www.elsr.co.uk/social"

    # Add to ics calendar
    new_cal = icsCalendar()
    new_cal.events.add(new_event)

    # Save as file
    filename = os.path.join(ICS_DIRECTORY, f"Social_{social.date}.ics")
    with open(filename, 'w') as my_file:
        my_file.writelines(new_cal.serialize_iter())

    # ----------------------------------------------------------- #
    # Send link to download the file
    # ----------------------------------------------------------- #
    download_name = f"ELSR_Social_{social.date}.ics"

    app.logger.debug(f"download_ics(): Serving ICS social_id = '{social_id}' ({social.date}), "
                     f"download_name = '{download_name}'.")
    EventRepository().log_event("ICS Downloaded", f"Serving ICS social_idd = '{social_id}' ({social.date}).")
    return send_from_directory(directory=ICS_DIRECTORY,
                               path=os.path.basename(filename),
                               download_name=download_name)
