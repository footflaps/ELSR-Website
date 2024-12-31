from flask import render_template, url_for, request, flash, redirect, abort, send_from_directory
from flask_login import current_user
from ics import Calendar as icsCalendar, Event as icsEvent
import os
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site, ICS_DIRECTORY


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.social_repository import SocialRepository, SOCIAL_DB_PRIVATE
from core.database.repositories.event_repository import EventRepository

from core.decorators.user_decorators import update_last_seen, logout_barred_user, login_required

from core.subs_dates import get_date_from_url


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Show all socials for a given date
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/social", methods=['GET'])
@logout_barred_user
@update_last_seen
def display_socials():
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
    social = SocialRepository().one_by_id(social_id)
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
