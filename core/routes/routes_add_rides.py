from flask import render_template, url_for, request, flash, redirect, abort
from flask_login import current_user
from werkzeug import exceptions
from datetime import datetime
import json
import os
from threading import Thread

# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, delete_file_if_exists, live_site, GRAVEL_CHOICE

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.user_repository import UserRepository
from core.database.repositories.cafe_repository import CafeRepository
from core.database.repositories.gpx_repository import GpxRepository, TYPE_ROAD, TYPE_GRAVEL
from core.database.repositories.calendar_repository import CalendarRepository, NEW_CAFE, UPLOAD_ROUTE, MEETING_OTHER, \
                                                   MEETING_BEAN, MEETING_COFFEE_VANS, DEFAULT_START_TIMES
from core.database.repositories.event_repository import EventRepository

from core.forms.calendar_forms import create_ride_form

from core.decorators.user_decorators import update_last_seen, logout_barred_user, login_required, rw_required

from core.subs_gpx import allowed_file, GPX_UPLOAD_FOLDER_ABS
from core.subs_gpx_edit import strip_excess_info_from_gpx
from core.subs_email_sms import send_ride_notification_emails
from core.subs_dates import get_date_from_url


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Add / Edit a new ride to the calendar
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/add_ride', methods=['GET', 'POST'])
@app.route('/edit_ride', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def add_ride():
    # ----------------------------------------------------------- #
    # Did we get passed a date or a ride_id? (Optional)
    # ----------------------------------------------------------- #
    start_date_str = get_date_from_url(return_none_if_empty=True)
    ride_id = request.args.get('ride_id', None)

    # ----------------------------------------------------------- #
    # Validate ride_id
    # ----------------------------------------------------------- #
    if ride_id:
        ride = CalendarRepository().one_ride_id(ride_id)
        if not ride:
            app.logger.debug(f"add_ride(): Failed to locate ride, ride_id = '{ride_id}'.")
            EventRepository().log_event("Edit Ride Fail", f"Failed to locate ride, ride_id = '{ride_id}'.")
            return abort(404)
    else:
        ride = None

    # ----------------------------------------------------------- #
    # Work out what we're doing (Add / Edit)
    # ----------------------------------------------------------- #
    if ride_id \
            and request.method == 'GET':
        # ----------------------------------------------------------- #
        # Edit event, so pre-fill form from dB
        # ----------------------------------------------------------- #
        # 1: Need to locate the GPX track used by the ride
        gpx = GpxRepository().one_gpx(ride.gpx_id)
        if not gpx:
            # Should never happen, but...
            app.logger.debug(f"add_ride(): Failed to locate gpx, ride_id  = '{ride_id}', "
                             f"ride.gpx_id = '{ride.gpx_id}'.")
            EventRepository().log_event("Edit Ride Fail", f"Failed to locate gpx, ride_id  = '{ride_id}', "
                                                f"ride.gpx_id = '{ride.gpx_id}'.")
            flash("Sorry, something went wrong..")
            return redirect(url_for('weekend', date=start_date_str))

        # 2: Need to locate the target cafe for the ride (might be a new cafe so None is acceptable)
        cafe = CafeRepository().one_cafe(ride.cafe_id)

        # 3: Need to locate the owner of the ride
        user = UserRepository().find_user_from_email(ride.email)
        if not user:
            # Should never happen, but...
            app.logger.debug(f"add_ride(): Failed to locate user, ride_id  = '{ride_id}', "
                             f"ride.email = '{ride.email}'.")
            EventRepository().log_event("Edit Ride Fail", f"Failed to locate user, ride_id  = '{ride_id}', "
                                                f"ride.email = '{ride.email}'.")
            flash("Sorry, something went wrong..")
            return redirect(url_for('weekend', date=start_date_str))

        # Select form based on Admin status
        form = create_ride_form(current_user.admin, gpx.id)

        # Date
        form.date.data = datetime.strptime(ride.date.strip(), '%d%m%Y')

        # Fill in Owner box (admin only)
        if current_user.admin:
            form.owner.data = user.combo_str

        # Ride leader
        form.leader.data = ride.leader

        # Start time and location
        start_details = split_start_string(ride.start_time)
        form.start_time.data = start_details['time']
        place = start_details['place']
        if place == MEETING_BEAN \
                or place == MEETING_COFFEE_VANS:
            # One of our two default locations
            form.start_location.data = place
        else:
            # "Other.." category
            form.start_location.data = MEETING_OTHER
            form.other_location.data = place

        # Cafe:
        if cafe:
            # One of our known set
            form.destination.data = cafe.combo_string
            form.new_destination.data = ""
        else:
            # Not in the database yet
            form.destination.data = NEW_CAFE
            form.new_destination.data = ride.destination

        # Pace / Group
        form.group.data = ride.group

        # Existing route
        form.gpx_name.data = gpx.combo_string

        # Change submission button name
        form.submit.label.text = "Update Ride"

        # Check if GPX route is still marked private
        if not gpx.public:
            flash(f"Warning the GPX file '{gpx.name}' is still PRIVATE")

        # Check if GPX file exists
        filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
        if not os.path.exists(filename):
            flash(f"Warning the GPX '{gpx.name}' file is MISSING! You can't use this route!")

    else:
        # ----------------------------------------------------------- #
        # Add event, so start with fresh form
        # ----------------------------------------------------------- #
        if current_user.admin:
            form = create_ride_form(True)
            if not ride and \
                    request.method == 'GET':
                form.owner.data = current_user.combo_str
        else:
            form = create_ride_form(False)

        # Pre-populate the data in the form, if we were passed one
        if start_date_str:
            start_date = datetime(int(start_date_str[4:8]), int(start_date_str[2:4]), int(start_date_str[0:2]), 0, 00)
            form.date.data = start_date

        # Assume the author is the group leader
        if not ride and \
                request.method == 'GET':
            form.leader.data = current_user.name

    # Are we posting the completed form?
    if request.method == 'POST' \
            and form.validate_on_submit():
        # ----------------------------------------------------------- #
        # Handle form passing validation
        # ----------------------------------------------------------- #

        # Detect cancel button
        if form.cancel.data:
            # Abort now...
            return redirect(url_for('weekend', date=start_date_str))

        # 1: Check we can find cafe in the dB
        if form.destination.data != NEW_CAFE:
            # Work out which cafe they selected in the drop down
            # eg "Goat and Grass (was curious goat) (46)"
            cafe_id = CafeRepository().cafe_id_from_combo_string(form.destination.data)
            cafe = CafeRepository().one_cafe(cafe_id)
            if not cafe:
                # Should never happen, but....
                app.logger.debug(f"add_ride(): Failed to get cafe from '{form.destination.data}'.")
                EventRepository().log_event("Add ride Fail", f"Failed to get cafe from '{form.destination.data}'.")
                flash("Sorry, something went wrong - couldn't understand the cafe choice.")
                return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                       live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                       MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)
        else:
            # New cafe, not yet in database
            cafe = None

        # 2: Validate GPX (must be specified)
        if form.gpx_name.data == UPLOAD_ROUTE \
                and not form.gpx_file.data:
            flash("You didn't select a GPX file to upload!")

        # 3: Check we can find gpx in the dB
        if form.gpx_name.data != UPLOAD_ROUTE:
            # Work out which GPX route they chose
            # eg "20: 'Mill End again', 107.6km / 838.0m"
            gpx_id = GpxRepository().gpx_id_from_combo_string(form.gpx_name.data)
            gpx = GpxRepository().one_gpx(gpx_id)
            if not gpx:
                # Should never happen, but....
                app.logger.debug(f"add_ride(): Failed to get GPX from '{form.gpx_name.data}'.")
                EventRepository().log_event("Add ride Fail", f"Failed to get GPX from '{form.gpx_name.data}'.")
                flash("Sorry, something went wrong - couldn't understand the GPX choice.")
                return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                       live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                       MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)
        else:
            # They are uploading their own GPX file
            gpx = None

        # 4: Check route passes cafe (if both from comboboxes)
        if gpx and cafe:
            match = False
            # gpx.cafes_passed is a json.dumps string, so need to convert back
            for cafe_passed in json.loads(gpx.cafes_passed):
                if int(cafe_passed["cafe_id"]) == cafe.id:
                    match = True
            if not match:
                # Doesn't look like we pass that cafe!
                flash(f"That GPX route doesn't pass {cafe.name}!")
                return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                       live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                       MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)

        # 5: Check they aren't nominating someone else (only Admins can nominate another person to lead a ride)
        if not current_user.admin:
            # Allow them to append eg "Simon" -> "Simon Bond" as some usernames are quite short
            if form.leader.data[0:len(current_user.name)] != current_user.name:
                # Looks like they've nominated someone else
                flash("Only Admins can nominate someone else to lead a ride.")
                # In case they've forgotten their username, reset it in the form
                form.leader.data = current_user.name
                return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                       live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                       MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)

        # ----------------------------------------------------------- #
        # Do we need to upload a GPX?
        # ----------------------------------------------------------- #
        if not gpx:
            if 'gpx_file' not in request.files:
                # Almost certain the form failed validation
                app.logger.debug(f"add_ride(): Failed to find 'gpx_file' in request.files!")
                EventRepository().log_event(f"New Ride Fail", f"Failed to find 'gpx_file' in request.files!")
                flash("Couldn't find the file.")
                return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                       live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                       MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)
            else:
                # Get the filename
                file = request.files['gpx_file']
                app.logger.debug(f"add_ride(): About to upload '{file}'.")

                # If the user does not select a file, the browser submits an
                # empty file without a filename.
                if file.filename == '':
                    app.logger.debug(f"add_ride(): No selected file!")
                    EventRepository().log_event(f"Add ride Fail", f"No selected file!")
                    flash('No selected file')
                    return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                           live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                           MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)

                if not file or \
                        not allowed_file(file.filename):
                    app.logger.debug(f"add_ride(): Invalid file '{file.filename}'!")
                    EventRepository().log_event(f"Add ride Fail", f"Invalid file '{file.filename}'!")
                    flash("That's not a GPX file!")
                    return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                           live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                           MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)

                # Create a new GPX object
                # We do this first as we need the id in order to create
                # the filename for the GPX file when we upload it
                gpx = GpxRepository()
                if form.destination.data != NEW_CAFE:
                    # Existing cafe, so use name from combobox, but strip off cafe.id in brackets
                    gpx.name = form.destination.data.split('(')[0]
                else:
                    # New cafe, so take name from new destination field
                    gpx.name = form.new_destination.data
                gpx.email = current_user.email
                gpx.cafes_passed = "[]"
                gpx.ascent_m = 0
                gpx.length_km = 0
                gpx.filename = "tmp"
                # Fill in the GPX surface type
                if form.group.data == GRAVEL_CHOICE:
                    gpx.type = TYPE_GRAVEL
                else:
                    gpx.type = TYPE_ROAD

                # Add to the dB
                new_id = gpx.add_gpx(gpx)
                if new_id:
                    # Success, added GPX to dB
                    # Have to re-get the GPX as it's changed since we created it
                    gpx = GpxRepository().one_gpx(new_id)
                    app.logger.debug(f"add_ride(): GPX added to dB, id = '{gpx.id}'.")
                    EventRepository().log_event(f"Add ride Success", f" GPX added to dB, gpx.id = '{gpx.id}'.")
                else:
                    # Failed to create new dB entry
                    app.logger.debug(f"add_ride(): Failed to add gpx to the dB!")
                    EventRepository().log_event(f"Add ride Fail", f"Failed to add gpx to the dB!")
                    flash("Sorry, something went wrong!")
                    return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                           live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                           MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)

                # This is where we will store it
                filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, f"gpx_{gpx.id}.gpx")
                app.logger.debug(f"add_ride(): Filename will be = '{filename}'.")

                # Make sure this doesn't already exist
                if not delete_file_if_exists(filename):
                    # Failed to delete existing file (func will generate error trace)
                    flash("Sorry, something went wrong!")
                    return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                           live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                           MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)

                # Upload the GPX file
                try:
                    file.save(filename)
                except Exception as e:
                    app.logger.debug(f"add_ride(): Failed to upload/save '{filename}', error code was {e.args}.")
                    EventRepository().log_event(f"Add ride Fail", f"Failed to upload/save '{filename}', error code was {e.args}.")
                    flash("Sorry, something went wrong!")
                    return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                           live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                           MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)

                # Update gpx object with filename
                if not GpxRepository().update_filename(gpx.id, filename):
                    app.logger.debug(f"add_ride(): Failed to update filename in the dB for gpx_id='{gpx.id}'.")
                    EventRepository().log_event(f"Add ride Fail", f"Failed to update filename in the dB for gpx_id='{gpx.id}'.")
                    flash("Sorry, something went wrong!")
                    return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                           live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                           MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)

                # Strip all excess data from the file
                strip_excess_info_from_gpx(filename, gpx.id, f"ELSR: {gpx.name}")
                app.logger.debug(f"add_ride(): New GPX added, gpx_id = '{gpx.id}', ({gpx.name}).")
                EventRepository().log_event(f"Add ride Success", f"New GPX added, gpx_id = '{gpx.id}', ({gpx.name}).")

        # ----------------------------------------------------------- #
        # We can now add / update the ride in the Calendar
        # ----------------------------------------------------------- #
        if ride:
            # Updating an existing ride
            new_ride = ride
        else:
            # New event
            new_ride = CalendarRepository()

        # Populate the calendar entry
        # Convert form date format '2023-06-23' to preferred format '23062023'
        start_date_str = form.date.data.strftime("%d%m%Y")

        new_ride.date = start_date_str
        new_ride.leader = form.leader.data
        # Create our ride start string eg "8:00am from Bean Theory Cafe"
        new_ride.start_time = create_start_string(form)
        if cafe:
            # Existing cafe from db
            new_ride.destination = cafe.name
            new_ride.cafe_id = cafe.id
        else:
            # New destination
            new_ride.destination = form.new_destination.data
            new_ride.cafe_id = None
        new_ride.group = form.group.data
        new_ride.gpx_id = gpx.id

        # Admin can allocate events to people
        if current_user.admin:
            # Get user
            user = UserRepository().user_from_combo_string(form.owner.data)
            if user:
                new_ride.email = user.email
            else:
                # Should never happen, but...
                app.logger.debug(f"add_ride(): Failed to locate user, ride_id  = '{ride_id}', "
                                 f"form.owner.data = '{form.owner.data}'.")
                EventRepository().log_event("Edit Ride Fail", f"Failed to locate user, ride_id  = '{ride_id}', "
                                                    f"form.owner.data = '{form.owner.data}'.")
                flash("Sorry, something went wrong..")
                return redirect(url_for('weekend', date=start_date_str))
        else:
            # Not admin, so user owns the ride event
            new_ride.email = current_user.email

        # Add to the dB
        new_ride = CalendarRepository().add_ride(new_ride)
        if new_ride:
            # Success
            app.logger.debug(f"add_ride(): Successfully added new ride.")
            EventRepository().log_event("Add ride Pass", f"Successfully added new_ride.")
            if ride:
                flash("Ride updated!")
            else:
                flash("Ride added to Calendar!")

            # Do they need to edit the just uploaded GPX file to make it public?
            if not gpx.public:
                # Forward them to the edit_route page to edit it and make it public
                flash("You need to edit your route and make it public before it can be added to the calendar!")
                return redirect(url_for('edit_route', gpx_id=gpx.id,
                                        return_path=f"{url_for('weekend', date=start_date_str)}"))
            else:
                # Send all the email notifications now as ride us public
                Thread(target=send_ride_notification_emails, args=(new_ride, )).start()
                # Go to Calendar page for this ride's date
                return redirect(url_for('weekend', date=start_date_str))
        else:
            # Should never happen, but...
            app.logger.debug(f"add_ride(): Failed to add ride from '{new_ride}'.")
            EventRepository().log_event("Add ride Fail", f"Failed to add ride '{new_ride}'.")
            flash("Sorry, something went wrong.")
            return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride,
                                   live_site=live_site(), DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                                   MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE, UPLOAD_ROUTE=UPLOAD_ROUTE)

    # ----------------------------------------------------------- #
    # Handle POST
    # ----------------------------------------------------------- #
    elif request.method == 'POST':

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('weekend', date=start_date_str))

        # This traps a post, but where the form verification failed.
        flash("Something was missing, see comments below:")
        return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride, live_site=live_site(),
                               DEFAULT_START_TIMES=DEFAULT_START_TIMES, MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE,
                               UPLOAD_ROUTE=UPLOAD_ROUTE)

    # ----------------------------------------------------------- #
    # Handle GET
    # ----------------------------------------------------------- #

    return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride, live_site=live_site(),
                           DEFAULT_START_TIMES=DEFAULT_START_TIMES, MEETING_OTHER=MEETING_OTHER, NEW_CAFE=NEW_CAFE,
                           UPLOAD_ROUTE=UPLOAD_ROUTE)


# -------------------------------------------------------------------------------------------------------------- #
# Delete a ride from the calendar
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/delete_ride", methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def delete_ride():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    ride_id = request.args.get('ride_id', None)
    date = get_date_from_url()
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
    if not ride_id:
        app.logger.debug(f"delete_ride(): Missing ride_id!")
        EventRepository().log_event("Delete Ride Fail", f"Missing ride_id!")
        return abort(400)
    if not date:
        app.logger.debug(f"delete_ride(): Missing date!")
        EventRepository().log_event("Delete Ride Fail", f"Missing date!")
        return abort(400)
    elif not password:
        app.logger.debug(f"delete_ride(): Missing password!")
        EventRepository().log_event("Delete Ride Fail", f"Missing password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check the ride_id is valid
    # ----------------------------------------------------------- #
    ride = CalendarRepository().one_ride_id(ride_id)
    if not ride:
        app.logger.debug(f"delete_ride(): Failed to locate ride with cafe_id = '{ride_id}'.")
        EventRepository().log_event("Delete Ride Fail", f"Failed to locate ride with cafe_id = '{ride_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Validate password against current_user's (admins)
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"make_admin(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        EventRepository().log_event("Make Admin Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('weekend', date=date))

    # ----------------------------------------------------------- #
    # Restrict access to Admin or Author
    # ----------------------------------------------------------- #
    if not current_user.admin \
            and current_user.email != ride.email:
        # Failed authentication
        app.logger.debug(f"delete_ride(): Rejected request from '{current_user.email}' as no permissions"
                         f" for ride_id = '{ride_id}'.")
        EventRepository().log_event("Delete Ride Fail", f"Rejected request from user '{current_user.email}' as no "
                                              f"permissions for ride_id = '{ride_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Delete event from calendar
    # ----------------------------------------------------------- #
    if CalendarRepository().delete_ride(ride_id):
        # Success
        app.logger.debug(f"delete_ride(): Successfully deleted the ride, ride_id = '{ride_id}'.")
        EventRepository().log_event("Delete Ride Success", f"Successfully deleted the ride. ride_id = '{ride_id}''.")
        flash("Ride deleted.")
    else:
        # Should never get here, but....
        app.logger.debug(f"delete_ride(): Failed to delete the ride, ride_id = '{ride_id}'.")
        EventRepository().log_event("Delete Ride Fail", f"Failed to delete the ride, ride_id = '{ride_id}'.")
        flash("Sorry, something went wrong!")

    # Back to weekend ride summary page for the day in question
    return redirect(url_for('weekend', date=date))
