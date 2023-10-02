from flask import render_template, url_for, request, flash, redirect, abort
from flask_login import login_required, current_user
from werkzeug import exceptions
from bbc_feeds import weather
from datetime import datetime, timedelta
import json
import os
from threading import Thread


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, delete_file_if_exists

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe, OPEN_CAFE_COLOUR, CLOSED_CAFE_COLOUR
from core.subs_google_maps import create_polyline_set, ELSR_HOME, MAP_BOUNDS, google_maps_api_key, count_map_loads
from core.dB_gpx import Gpx
from core.subs_gpx import allowed_file, GPX_UPLOAD_FOLDER_ABS
from core.dB_events import Event
from core.db_users import User, update_last_seen, logout_barred_user
from core.subs_graphjs import get_elevation_data_set, get_destination_cafe_height
from core.db_calendar import Calendar, create_ride_form, NEW_CAFE, UPLOAD_ROUTE, DEFAULT_START
from core.subs_gpx_edit import strip_excess_info_from_gpx
from core.subs_email_sms import send_ride_notification_emails


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

CAMBRIDGE_BBC_WEATHER_CODE = 2653941


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def work_out_days(target_date_str):

    # Step 1: Create a set of date strings eg ["23082023", "24082023" ]
    if target_date_str:
        # ----------------------------------------------------------- #
        # Scenario #1 - Passed a specific date, so find that day
        # ----------------------------------------------------------- #
        # NB We may have been parsed garbage as the date
        try:
            target_date = datetime(int(target_date_str[4:8]), int(target_date_str[2:4]), int(target_date_str[0:2]), 0, 00)
        except:
            # Flag back fail
            return None

        # Get the day of week
        day_str = target_date.strftime("%A")

        # If it's a Sat or Sunday, we'll show the full WE
        if day_str == "Saturday":
            days = ["Saturday", "Sunday"]
            dates_short = {
                "Saturday": target_date.strftime("%d%m%Y"),
                "Sunday": (target_date + timedelta(days=1)).strftime("%d%m%Y")
            }

        elif day_str == "Sunday":
            days = ["Saturday", "Sunday"]
            dates_short = {
                "Saturday": (target_date - timedelta(days=1)).strftime("%d%m%Y"),
                "Sunday":   target_date.strftime("%d%m%Y")
            }

        else:
            # Just use that single day for now
            days = [day_str]
            dates_short = {
                day_str: target_date.strftime("%d%m%Y")
            }

    else:
        # ----------------------------------------------------------- #
        # Scenario #2 - no date given, so this / next weekend
        # ----------------------------------------------------------- #

        # No date, so either this weekend or next weekend if it's a weekday.
        today_str = datetime.today().strftime("%A")
        today = datetime.today()
        days = ["Saturday", "Sunday"]
        if today_str == "Saturday":
            # Today and tomorrow
            dates_short = {
                "Saturday": today.strftime("%d%m%Y"),
                "Sunday":  (today + timedelta(days=1)).strftime("%d%m%Y")
            }

        elif today_str == "Sunday":
            # Yesterday and today
            dates_short = {
                "Saturday": (today - timedelta(days=1)).strftime("%d%m%Y"),
                "Sunday":  today.strftime("%d%m%Y")
        }

        else:
            # Next weekend
            saturday = today + timedelta((5 - today.weekday()) % 7)
            dates_short = {
                "Saturday": saturday.strftime("%d%m%Y"),
                "Sunday":   (saturday + timedelta(days=1)).strftime("%d%m%Y")
            }

    # ----------------------------------------------------------- #
    # Detect BHs
    # ----------------------------------------------------------- #

    # Ignore case of just one day eg a random Wednesday
    if len(days) > 1:
        # ----------------------------------------------------------- #
        # Do we have any rides on the Friday?
        # ----------------------------------------------------------- #
        # Convert "23082023" -> datetime object -> "22082023"
        friday_date = datetime(int(dates_short["Saturday"][4:8]), int(dates_short["Saturday"][2:4]),
                               int(dates_short["Saturday"][0:2]), 0, 00) - timedelta(days=1)
        friday_date_str = friday_date.strftime("%d%m%Y")
        # Do we have any rides in the dB
        if Calendar().all_calendar_date(friday_date_str):
            # We a ride on the Friday, so pre-pend Friday
            days.insert(0, "Friday")
            dates_short["Friday"] = friday_date_str

        # ----------------------------------------------------------- #
        # Do we have any rides on the Monday?
        # ----------------------------------------------------------- #
        # Convert "23082023" -> datetime object -> "24082023"
        monday_date = datetime(int(dates_short["Sunday"][4:8]), int(dates_short["Sunday"][2:4]),
                               int(dates_short["Sunday"][0:2]), 0, 00) + timedelta(days=1)
        monday_date_str = monday_date.strftime("%d%m%Y")
        # Do we have any rides in the dB
        if Calendar().all_calendar_date(monday_date_str):
            # We a ride on the Friday, so append Monday
            days.append("Monday")
            dates_short["Monday"] = monday_date_str

    # ----------------------------------------------------------- #
    # Add long form dates
    # ----------------------------------------------------------- #

    # Set of strings for webpage title line etc
    # {
    #   "Saturday": "Saturday 25 August 2023",
    #   "Sunday":   "Sunday 26 August 2023",
    # }
    dates_long = {}

    for day in days:
        # Convert string to datetime object
        short_date = dates_short[day]
        target_date = datetime(int(short_date[4:8]), int(short_date[2:4]), int(short_date[0:2]), 0, 00)
        dates_long[day] = target_date.strftime("%A %b %d %Y")

    # ----------------------------------------------------------- #
    # Return the three data sets
    # ----------------------------------------------------------- #

    return [days, dates_long, dates_short]


# -------------------------------------------------------------------------------------------------------------- #
# Weekend ride details
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/weekend', methods=['GET'])
@logout_barred_user
@update_last_seen
def weekend():
    # ----------------------------------------------------------- #
    # Did we get passed a date? (Optional)
    # ----------------------------------------------------------- #
    target_date_str = request.args.get('date', None)

    # ----------------------------------------------------------- #
    # Workout which weekend we're displaying
    # ----------------------------------------------------------- #
    tmp = work_out_days(target_date_str)

    # The above returns None if the date was garbage
    if not tmp:
        # Fed invalid date
        app.logger.debug(f"weekend(): Failed to understand target_date_str = '{target_date_str}'.")
        Event().log_event("Weekend Fail", f"Failed to understand target_date_str = '{target_date_str}'.")
        return abort(404)
    else:
        # Get what we actually wanted from work_out_days()
        days = tmp[0]
        dates_long = tmp[1]
        dates_short = tmp[2]

    # ----------------------------------------------------------- #
    # Add GPX details
    # ----------------------------------------------------------- #

    # We will populate these dictionaries for each day
    rides = {}
    gpxes = {}
    cafe_coords = {}
    cafes = {}
    start_times = {}

    # We will flash a warning if we find a private GPX in any of the weekend's routes
    private_gpx = False

    # Populate everything for Saturday
    for day in days:

        # We need to check all the GPXes still exist etc
        tmp_rides = Calendar().all_calendar_date(dates_short[day])
        # app.logger.debug(f"weekend(): Passed '{dates_short[day]}' to calendar and got back '{tmp_rides}'")

        # Create empty sets for all the data we will need to populate for each day
        rides[day] = []
        gpxes[day] = []
        cafes[day] = []
        start_times[day] = []
        cafe_coords[day] = []

        for ride in tmp_rides:
            # Look up the ride
            gpx = Gpx().one_gpx(ride.gpx_id)

            # Should exist, but..
            if gpx:
                # Double check we can find the file
                filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
                if os.path.exists(filename):

                    # Extract ride stats
                    ride.distance = gpx.length_km
                    ride.elevation = gpx.ascent_m
                    ride.public = gpx.public()
                    if ride.start_time:
                        if ride.start_time.strip() != DEFAULT_START \
                                and ride.start_time.strip() != "":
                            start_times[day].append(f"{ride.destination}: {ride.start_time}")

                    # Make a note, if we find a non public GPX
                    if not gpx.public():
                        private_gpx = True

                    # Update destination (as cafe may have changed name)
                    if ride.cafe_id:
                        cafe = Cafe().one_cafe(ride.cafe_id)
                        if cafe:
                            ride.destination = cafe.name

                    # Add gpx object to the list of GPX files for that day
                    gpxes[day].append(gpx)

                    # Add ride to the list of rides that day
                    rides[day].append(ride)

                    # Look up the cafe
                    cafe = Cafe().one_cafe(ride.cafe_id)

                    # NB Might not exist if a new cafe, not in our existing db
                    if cafe:
                        cafe_coords[day].append({
                            "position": {"lat": cafe.lat, "lng": cafe.lon},
                            "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
                            "color": OPEN_CAFE_COLOUR,
                        })
                        cafes[day].append(cafe)
                    else:
                        # Just add a blank cafe object
                        cafes[day].append(Cafe())
                else:
                    # Missing GPX file
                    app.logger.debug(f"weekend(): Failed to locate GPX file, ride_id = '{ride.id}'.")
                    Event().log_event("Weekend Fail", f"Failed to locate GPX file, ride_id = '{ride.id}'.")
                    flash(f"Looks like GPX file for ride {ride.id} has been deleted!")
            else:
                # Missing GPX row in the table
                app.logger.debug(f"weekend(): Failed to locate GPX entry, ride_id = '{ride.id}'.")
                Event().log_event("Weekend Fail", f"Failed to locate GPX entry, ride_id = '{ride.id}'.")
                flash(f"Looks like GPX route for ride {ride.id} has been deleted (Saturday)!")

    # ----------------------------------------------------------- #
    # Polylines for the GPX files
    # ----------------------------------------------------------- #
    polylines = {}
    for day in days:
        polylines[day] = create_polyline_set(gpxes[day])

    # ----------------------------------------------------------- #
    # Keep track of map loads
    # ----------------------------------------------------------- #
    for day in days:
        if rides[day]:
            # Weekend page has one map per day
            count_map_loads(1)

    # ----------------------------------------------------------- #
    # Get elevation graph data
    # ----------------------------------------------------------- #
    elevation_data = {}
    elevation_cafes = {}
    for day in days:
        elevation_data[day] = get_elevation_data_set(gpxes[day])
        elevation_cafes[day] = get_destination_cafe_height(elevation_data[day], gpxes[day], cafes[day])

    # ----------------------------------------------------------- #
    # Get weather
    # ----------------------------------------------------------- #
    bbc_weather = weather().forecast(CAMBRIDGE_BBC_WEATHER_CODE)
    today = datetime.today().strftime("%A")

    weather_data = {}
    for day in days:

        for item in bbc_weather:
            title = item['title'].split(':')
            if title[0] == day \
                    or today == day and title == "Today":
                weather_data[day] = item['summary'].split(',')[0:7]

    # ----------------------------------------------------------- #
    # Render the page
    # ----------------------------------------------------------- #

    if private_gpx:
        flash("One or more routes hasn't been made public yet!")

    flash("Now meeting at Bean Theory Cafe!")

    return render_template("calendar_weekend.html", year=current_year,
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), ELSR_HOME=ELSR_HOME, MAP_BOUNDS=MAP_BOUNDS,
                           days=days, dates_long=dates_long, dates_short=dates_short, DEFAULT_START=DEFAULT_START,
                           rides=rides, start_times=start_times, weather_data=weather_data,
                           polylines=polylines, cafe_coords=cafe_coords,
                           elevation_data=elevation_data, elevation_cafes=elevation_cafes, anchor=target_date_str)


# -------------------------------------------------------------------------------------------------------------- #
# Add / Edit a new ride to the calendar
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/add_ride', methods=['GET', 'POST'])
@app.route('/edit_ride', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def add_ride():
    # ----------------------------------------------------------- #
    # Did we get passed a date or a ride_id? (Optional)
    # ----------------------------------------------------------- #
    start_date_str = request.args.get('date', None)
    ride_id = request.args.get('ride_id', None)

    # ----------------------------------------------------------- #
    # Permissions
    # ----------------------------------------------------------- #
    if not current_user.readwrite():
        # Failed authentication
        app.logger.debug(f"add_ride(): Refusing permission for '{current_user.email}'.")
        Event().log_event("Add Ride Fail", f"Refusing permission for '{current_user.email}'.")
        flash("You do not have permission to add events to the calendar.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Validate ride_id
    # ----------------------------------------------------------- #
    if ride_id:
        ride = Calendar().one_ride_id(ride_id)
        if not ride:
            app.logger.debug(f"add_ride(): Failed to locate ride, ride_id = '{ride_id}'.")
            Event().log_event("Edit Ride Fail", f"Failed to locate ride, ride_id = '{ride_id}'.")
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
        gpx = Gpx().one_gpx(ride.gpx_id)
        if not gpx:
            # Should never happen, but...
            app.logger.debug(f"add_ride(): Failed to locate gpx, ride_id  = '{ride_id}', "
                             f"ride.gpx_id = '{ride.gpx_id}'.")
            Event().log_event("Edit Ride Fail", f"Failed to locate gpx, ride_id  = '{ride_id}', "
                                                f"ride.gpx_id = '{ride.gpx_id}'.")
            flash("Sorry, something went wrong..")
            return redirect(url_for('weekend', date=start_date_str))

        # 2: Need to locate the target cafe for the ride (might be a new cafe so None is acceptable)
        cafe = Cafe().one_cafe(ride.cafe_id)

        # 3: Need to locate the owner of the ride
        user = User().find_user_from_email(ride.email)
        if not user:
            # Should never happen, but...
            app.logger.debug(f"add_ride(): Failed to locate user, ride_id  = '{ride_id}', "
                             f"ride.email = '{ride.email}'.")
            Event().log_event("Edit Ride Fail", f"Failed to locate user, ride_id  = '{ride_id}', "
                                                f"ride.email = '{ride.email}'.")
            flash("Sorry, something went wrong..")
            return redirect(url_for('weekend', date=start_date_str))

        # Select form based on Admin status
        form = create_ride_form(current_user.admin())

        # Date
        form.date.data = datetime.strptime(ride.date.strip(), '%d%m%Y')

        # Fill in Owner box (admin only)
        if current_user.admin():
            form.owner.data = user.combo_str()

        # Ride leader
        form.leader.data = ride.leader

        # Start time
        if not form.start.data:
            form.start.data = ride.start_time

        # Cafe:
        if cafe:
            form.destination.data = cafe.combo_string()
            form.new_destination.data = ""
        else:
            form.destination.data = NEW_CAFE
            form.new_destination.data = ride.destination

        # Pace / Group
        form.group.data = ride.group

        # Existing route
        form.gpx_name.data = gpx.combo_string()

        # Change submission button name
        form.submit.label.text = "Update Ride"

    else:
        # ----------------------------------------------------------- #
        # Add event, so start with fresh form
        # ----------------------------------------------------------- #
        if current_user.admin():
            form = create_ride_form(True)
            if not ride:
                form.owner.data = current_user.combo_str()
        else:
            form = create_ride_form(False)

        if request.method == 'GET':
            form.start.data = DEFAULT_START

        # Pre-populate the data in the form, if we were passed one
        if start_date_str:
            start_date = datetime(int(start_date_str[4:8]), int(start_date_str[2:4]), int(start_date_str[0:2]), 0, 00)
            form.date.data = start_date

        # Assume the author is the group leader
        if not ride:
            form.leader.data = current_user.name

    # Are we posting the completed comment form?
    if request.method == 'POST' \
            and form.validate_on_submit():
        # ----------------------------------------------------------- #
        # Handle form passing validation
        # ----------------------------------------------------------- #

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('weekend', date=start_date_str))

        # 1: Validate date (must be in the future)
        if type(form.date.data) == datetime:
            formdate = form.date.data.date()
        else:
            formdate = form.date.data
        today = datetime.today().date()
        print(f"formdate is '{type(formdate)}', today is '{type(today)}'")
        app.logger.debug(f"formdate is '{type(formdate)}', today is '{type(today)}'")
        if formdate < today and \
                not current_user.admin():
            flash("The date is in the past!")
            return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)

        # 2: Validate cafe (must be specified)
        if form.destination.data == NEW_CAFE \
                and form.new_destination.data == "":
            flash("New cafe not specified!")
            return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)

        # 3: Check we can find cafe in the dB
        if form.destination.data != NEW_CAFE:
            # Work out which cafe they selected in the drop down
            # eg "Goat and Grass (was curious goat) (46)"
            cafe_id = Cafe().cafe_id_from_combo_string(form.destination.data)
            cafe = Cafe().one_cafe(cafe_id)
            if not cafe:
                # Should never happen, but....
                app.logger.debug(f"add_ride(): Failed to get cafe from '{form.destination.data}'.")
                Event().log_event("Add ride Fail", f"Failed to get cafe from '{form.destination.data}'.")
                flash("Sorry, something went wrong - couldn't understand the cafe choice.")
                return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)
        else:
            # New cafe, not yet in database
            cafe = None

        # 4: Validate GPX (must be specified)
        if form.gpx_name.data == UPLOAD_ROUTE \
                and not form.gpx_file.data:
            flash("You didn't select a GPX file to upload!")

        # 5: Check we can find gpx in the dB
        if form.gpx_name.data != UPLOAD_ROUTE:
            # Work out which GPX route they chose
            # eg "20: 'Mill End again', 107.6km / 838.0m"
            gpx_id = Gpx().gpx_id_from_combo_string(form.gpx_name.data)
            gpx = Gpx().one_gpx(gpx_id)
            if not gpx:
                # Should never happen, but....
                app.logger.debug(f"add_ride(): Failed to get GPX from '{form.gpx_name.data}'.")
                Event().log_event("Add ride Fail", f"Failed to get GPX from '{form.gpx_name.data}'.")
                flash("Sorry, something went wrong - couldn't understand the GPX choice.")
                return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)
        else:
            # They are uploading their own GPX file
            gpx = None

        # 6: Check route passes cafe (if both from comboboxes)
        if gpx and cafe:
            match = False
            # gpx.cafes_passed is a json.dumps string, so need to convert back
            for cafe_passed in json.loads(gpx.cafes_passed):
                if int(cafe_passed["cafe_id"]) == cafe.id:
                    match = True
            if not match:
                # Doesn't look like we pass that cafe!
                flash(f"That GPX route doesn't pass {cafe.name}!")
                return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)

        # 7: Check they aren't nominating someone else (only Admins can nominate another person to lead a ride)
        if not current_user.admin():
            # Allow them to append eg "Simon" -> "Simon Bond" as some user names are quite short
            if form.leader.data[0:len(current_user.name)] != current_user.name:
                # Looks like they've nominated someone else
                flash("Only Admins can nominate someone else to lead a ride.")
                # In case they've forgotten their user name, reset it in the form
                form.leader.data = current_user.name
                return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)

        # ----------------------------------------------------------- #
        # Do we need to upload a GPX?
        # ----------------------------------------------------------- #
        if not gpx:
            if 'gpx_file' not in request.files:
                # Almost certain the form failed validation
                app.logger.debug(f"add_ride(): Failed to find 'gpx_file' in request.files!")
                Event().log_event(f"New Ride Fail", f"Failed to find 'gpx_file' in request.files!")
                flash("Couldn't find the file.")
                return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)
            else:
                # Get the filename
                file = request.files['gpx_file']
                app.logger.debug(f"add_ride(): About to upload '{file}'.")

                # If the user does not select a file, the browser submits an
                # empty file without a filename.
                if file.filename == '':
                    app.logger.debug(f"add_ride(): No selected file!")
                    Event().log_event(f"Add ride Fail", f"No selected file!")
                    flash('No selected file')
                    return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)

                if not file or \
                        not allowed_file(file.filename):
                    app.logger.debug(f"add_ride(): Invalid file '{file.filename}'!")
                    Event().log_event(f"Add ride Fail", f"Invalid file '{file.filename}'!")
                    flash("That's not a GPX file!")
                    return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)

                # Create a new GPX object
                # We do this first as we need the id in order to create
                # the filename for the GPX file when we upload it
                gpx = Gpx()
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

                # Add to the dB
                new_id = gpx.add_gpx(gpx)
                if new_id:
                    # Success, added GPX to dB
                    # Have to re-get the GPX as it's changed since we created it
                    gpx = Gpx().one_gpx(new_id)
                    app.logger.debug(f"add_ride(): GPX added to dB, id = '{gpx.id}'.")
                    Event().log_event(f"Add ride Success", f" GPX added to dB, gpx.id = '{gpx.id}'.")
                else:
                    # Failed to create new dB entry
                    app.logger.debug(f"add_ride(): Failed to add gpx to the dB!")
                    Event().log_event(f"Add ride Fail", f"Failed to add gpx to the dB!")
                    flash("Sorry, something went wrong!")
                    return render_template("gpx_add.html", year=current_year, form=form)

                # This is where we will store it
                filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, f"gpx_{gpx.id}.gpx")
                app.logger.debug(f"add_ride(): Filename will be = '{filename}'.")

                # Make sure this doesn't already exist
                if not delete_file_if_exists(filename):
                    # Failed to delete existing file (func will generate error trace)
                    flash("Sorry, something went wrong!")
                    return render_template("gpx_add.html", year=current_year, form=form)

                # Upload the GPX file
                try:
                    file.save(filename)
                except Exception as e:
                    app.logger.debug(f"add_ride(): Failed to upload/save '{filename}', error code was {e.args}.")
                    Event().log_event(f"Add ride Fail", f"Failed to upload/save '{filename}', error code was {e.args}.")
                    flash("Sorry, something went wrong!")
                    return render_template("gpx_add.html", year=current_year, form=form)

                # Update gpx object with filename
                if not Gpx().update_filename(gpx.id, filename):
                    app.logger.debug(f"add_ride(): Failed to update filename in the dB for gpx_id='{gpx.id}'.")
                    Event().log_event(f"Add ride Fail", f"Failed to update filename in the dB for gpx_id='{gpx.id}'.")
                    flash("Sorry, something went wrong!")
                    return render_template("gpx_add.html", year=current_year, form=form)

                # Strip all excess data from the file
                strip_excess_info_from_gpx(filename, gpx.id, f"ELSR: {gpx.name}")
                app.logger.debug(f"add_ride(): New GPX added, gpx_id = '{gpx.id}', ({gpx.name}).")
                Event().log_event(f"Add ride Success", f"New GPX added, gpx_id = '{gpx.id}', ({gpx.name}).")

        # ----------------------------------------------------------- #
        # We can now add / update the ride in the Calendar
        # ----------------------------------------------------------- #
        if ride:
            # Updating an existing ride
            new_ride = ride
        else:
            # New event
            new_ride = Calendar()

        # Populate the calendar entry
        # Convert form date format '2023-06-23' to preferred format '23062023'
        start_date_str = form.date.data.strftime("%d%m%Y")

        new_ride.date = start_date_str
        new_ride.leader = form.leader.data
        new_ride.start_time = form.start.data
        if cafe:
            new_ride.destination = cafe.name
            new_ride.cafe_id = cafe.id
        else:
            new_ride.destination = form.new_destination.data
            new_ride.cafe_id = None
        new_ride.group = form.group.data
        new_ride.gpx_id = gpx.id

        # Admin can allocate events to people
        if current_user.admin():
            # Get user
            user = User().user_from_combo_string(form.owner.data)
            if user:
                new_ride.email = user.email
            else:
                # Should never happen, but...
                app.logger.debug(f"add_ride(): Failed to locate user, ride_id  = '{ride_id}', "
                                 f"form.owner.data = '{form.owner.data}'.")
                Event().log_event("Edit Ride Fail", f"Failed to locate user, ride_id  = '{ride_id}', "
                                                    f"form.owner.data = '{form.owner.data}'.")
                flash("Sorry, something went wrong..")
                return redirect(url_for('weekend', date=start_date_str))
        else:
            # Not admin, so user owns the ride event
            new_ride.email = current_user.email

        # Add to the dB
        new_ride = Calendar().add_ride(new_ride)
        if new_ride:
            # Success
            app.logger.debug(f"add_ride(): Successfully added new ride.")
            Event().log_event("Add ride Pass", f"Successfully added new_ride.")
            if ride:
                flash("Ride updated!")
            else:
                flash("Ride added to Calendar!")
                # Send all the email notifications
                Thread(target=send_ride_notification_emails, args=(new_ride,)).start()

            # Do they need to edit the just uploaded GPX file to make it public?
            if not gpx.public():
                # Forward them to the edit_route page to edit it and make it public
                flash("You need to edit your route and make it public before it can be added to the calendar!")
                return redirect(url_for('edit_route', gpx_id=gpx.id,
                                        return_path=f"{url_for('weekend', date=start_date_str)}"))
            else:
                # Go to Calendar page for this ride's date
                return redirect(url_for('weekend', date=start_date_str))
        else:
            # Should never happen, but...
            app.logger.debug(f"add_ride(): Failed to add ride from '{new_ride}'.")
            Event().log_event("Add ride Fail", f"Failed to add ride '{new_ride}'.")
            flash("Sorry, something went wrong.")
            return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)

    # ----------------------------------------------------------- #
    # Handle POST
    # ----------------------------------------------------------- #
    elif request.method == 'POST':

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('weekend', date=start_date_str))

        # This traps a post, but where the form verification failed.
        flash("Something was missing, see comments below:")
        return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)

    # ----------------------------------------------------------- #
    # Handle GET
    # ----------------------------------------------------------- #

    return render_template("calendar_add_ride.html", year=current_year, form=form, ride=ride)


# -------------------------------------------------------------------------------------------------------------- #
# Delete a ride from the calendar
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/delete_ride", methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def delete_ride():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    ride_id = request.args.get('ride_id', None)
    date = request.args.get('date', None)
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
        Event().log_event("Delete Ride Fail", f"Missing ride_id!")
        return abort(400)
    if not date:
        app.logger.debug(f"delete_ride(): Missing date!")
        Event().log_event("Delete Ride Fail", f"Missing date!")
        return abort(400)
    elif not password:
        app.logger.debug(f"delete_ride(): Missing password!")
        Event().log_event("Delete Ride Fail", f"Missing password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check the ride_id is valid
    # ----------------------------------------------------------- #
    ride = Calendar().one_ride_id(ride_id)

    if not ride:
        app.logger.debug(f"delete_ride(): Failed to locate ride with cafe_id = '{ride_id}'.")
        Event().log_event("Delete Ride Fail", f"Failed to locate ride with cafe_id = '{ride_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Validate password against current_user's (admins)
    # ----------------------------------------------------------- #
    if not current_user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"make_admin(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
        Event().log_event("Make Admin Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for {current_user.name}.")
        return redirect(url_for('weekend', date=date))

    # ----------------------------------------------------------- #
    # Restrict access to Admin or owner of ride event
    # ----------------------------------------------------------- #
    if not current_user.admin() \
            and current_user.email != ride.email or \
            not current_user.readwrite():
        # Failed authentication
        app.logger.debug(f"delete_ride(): Rejected request from '{current_user.email}' as no permissions"
                         f" for ride_id = '{ride_id}'.")
        Event().log_event("Delete Ride Fail", f"Rejected request from user '{current_user.email}' as no "
                                              f"permissions for ride_id = '{ride_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Delete event from calendar
    # ----------------------------------------------------------- #
    if Calendar().delete_ride(ride_id):
        # Success
        app.logger.debug(f"delete_ride(): Successfully deleted the ride, ride_id = '{ride_id}'.")
        Event().log_event("Delete Ride Success", f"Successfully deleted the ride. ride_id = '{ride_id}''.")
        flash("Ride deleted.")
    else:
        # Should never get here, but....
        app.logger.debug(f"delete_ride(): Failed to delete the ride, ride_id = '{ride_id}'.")
        Event().log_event("Delete Ride Fail", f"Failed to delete the ride, ride_id = '{ride_id}'.")
        flash("Sorry, something went wrong!")

    # Back to weekend ride summary page for the day in question
    return redirect(url_for('weekend', date=date))
