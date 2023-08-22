from flask import render_template, url_for, request, flash, redirect, abort
from flask_login import login_required, current_user
from werkzeug import exceptions
from bbc_feeds import weather
from datetime import datetime, timedelta
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe, OPEN_CAFE_COLOUR, CLOSED_CAFE_COLOUR
from core.subs_google_maps import create_polyline_set, MAX_NUM_GPX_PER_GRAPH, ELSR_HOME, MAP_BOUNDS, GOOGLE_MAPS_API_KEY
from core.dB_gpx import Gpx
from core.dB_events import Event
from core.db_users import User, update_last_seen, logout_barred_user
from core.subs_graphjs import get_elevation_data_set, get_destination_cafe_height
from core.db_calendar import Calendar, CreateRideForm, NEW_CAFE, UPLOAD_ROUTE

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


# -------------------------------------------------------------------------------------------------------------- #
# Weekend ride details
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/weekend', methods=['GET'])
@update_last_seen
def weekend():
    # ----------------------------------------------------------- #
    # Did we get passed a date? (Optional)
    # ----------------------------------------------------------- #
    target_date_str = request.args.get('date', None)

    # ----------------------------------------------------------- #
    # Workout which weekend we're displaying
    # ----------------------------------------------------------- #
    if target_date_str:
        # Passed a specific date, so find that day / weekend
        target_date = datetime(int(target_date_str[4:8]), int(target_date_str[2:4]), int(target_date_str[0:2]), 0, 00)

        # We normally display the full weekend
        if target_date.strftime("%A") == "Saturday":
            # Passed a Saturday
            target_saturday = target_date
            target_sunday = target_date + timedelta(days=1)
        elif target_date.strftime("%A") == "Sunday":
            # Passed a Sunday
            target_saturday = target_date - timedelta(days=1)
            target_sunday = target_date
        else:
            # Another random day, so just show one day
            target_saturday = target_date
            target_sunday = None

        # These are our required data vars for the webpage
        saturday_date = target_saturday.strftime("%d%m%Y")
        saturday = target_saturday.strftime("%A %b %d %Y")
        if target_sunday:
            sunday_date = target_sunday.strftime("%d%m%Y")
            sunday = target_sunday.strftime("%A %b %d %Y")
        else:
            sunday_date = None
            sunday = ""
    else:
        # No date, so either this weekend or next weekend if it's a weekday.
        today_str = datetime.today().strftime("%A")
        today = datetime.today()
        if today_str == "Saturday":
            # Today and tomorrow
            tomorrow = today + timedelta(days=1)
            saturday_date = today.strftime("%d%m%Y")
            sunday_date = tomorrow.strftime("%d%m%Y")
            saturday = today.strftime("%A %b %d %Y")
            sunday = tomorrow.strftime("%A %b %d %Y")
        elif today_str == "Sunday":
            # Yesterday and today
            yesterday = today - timedelta(days=1)
            saturday_date = yesterday.strftime("%d%m%Y")
            sunday_date = today.strftime("%d%m%Y")
            saturday = yesterday.strftime("%A %b %d %Y")
            sunday = today.strftime("%A %b %d %Y")
        else:
            # Next weekend
            next_saturday = today + timedelta((5 - today.weekday()) % 7)
            next_sunday = today + timedelta((6 - today.weekday()) % 7)
            saturday_date = next_saturday.strftime("%d%m%Y")
            sunday_date = next_sunday.strftime("%d%m%Y")
            saturday = next_saturday.strftime("%A %b %d %Y")
            sunday = next_sunday.strftime("%A %b %d %Y")

    # ----------------------------------------------------------- #
    # Get the ride list
    # ----------------------------------------------------------- #
    saturday_rides = Calendar().all_calendar_date(saturday_date)
    sunday_rides = Calendar().all_calendar_date(sunday_date)

    # ----------------------------------------------------------- #
    # Add GPX details
    # ----------------------------------------------------------- #

    # We will flash a warning if we find a private GPX in any of the weekend's routes
    private_gpx = False

    # Need a set of GPX objects for maps and elevation plots
    saturday_gpxes = []
    sunday_gpxes = []

    # Need a set of cafe coordinates for the elevation graphs, to show where the cafes are
    saturday_cafes_elevations = []
    sunday_cafes_elevations = []

    # Just a set of cafes for the elevation graphs
    sat_cafes = []
    sun_cafes = []

    # Populate everything for Saturday
    for ride in saturday_rides:
        # Look up the ride
        gpx = Gpx().one_gpx(ride.gpx_id)

        # Should exist, but..
        if gpx:
            ride.distance = gpx.length_km
            ride.elevation = gpx.ascent_m
            ride.public = gpx.public()
            if not gpx.public():
                private_gpx = True
            saturday_gpxes.append(gpx)

        # Look up the cafe
        cafe = Cafe().one_cafe(ride.cafe_id)

        # Might not exist if a new cafe
        if cafe:
            saturday_cafes_elevations.append({
                "position": {"lat": cafe.lat, "lng": cafe.lon},
                "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
                "color": OPEN_CAFE_COLOUR,
            })
            sat_cafes.append(cafe)
        else:
            # Just add a blank cafe object
            sat_cafes.append(Cafe())

    # Populate everything for Sunday
    for ride in sunday_rides:
        # Look up the ride
        gpx = Gpx().one_gpx(ride.gpx_id)

        # Should exist, but..
        if gpx:
            ride.distance = gpx.length_km
            ride.elevation = gpx.ascent_m
            ride.public = gpx.public()
            if not gpx.public():
                private_gpx = True
            sunday_gpxes.append(gpx)

        # Look up the cafe
        cafe = Cafe().one_cafe(ride.cafe_id)

        # Might not exist if a new cafe
        if cafe:
            sunday_cafes_elevations.append({
                "position": {"lat": cafe.lat, "lng": cafe.lon},
                "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
                "color": OPEN_CAFE_COLOUR,
            })
            sun_cafes.append(cafe)
        else:
            # Just add a blank cafe object
            sun_cafes.append(Cafe())

    # ----------------------------------------------------------- #
    # Polylines for the GPX files
    # ----------------------------------------------------------- #
    saturday_polylines = create_polyline_set(saturday_gpxes)
    sunday_polylines = create_polyline_set(sunday_gpxes)

    # ----------------------------------------------------------- #
    # Get elevation data
    # ----------------------------------------------------------- #
    # Elevation traces
    saturday_elevation_data = get_elevation_data_set(saturday_gpxes)
    sunday_elevation_data = get_elevation_data_set(sunday_gpxes)

    # We need x,y traces for the cafes, so they appear at the right point on the elevation graphs
    saturday_elevation_cafes = get_destination_cafe_height(saturday_elevation_data, saturday_gpxes, sat_cafes)
    sunday_elevation_cafes = get_destination_cafe_height(sunday_elevation_data, sunday_gpxes, sun_cafes)

    # ----------------------------------------------------------- #
    # Get weather
    # ----------------------------------------------------------- #
    bbc_weather = weather().forecast(CAMBRIDGE_BBC_WEATHER_CODE)
    saturday_weather = None
    sunday_weather = None
    today = datetime.today().strftime("%A")
    for item in bbc_weather:
        title = item['title'].split(':')
        if title[0] == "Saturday" \
                or today == "Saturday" and title == "Today":
            saturday_weather = item['summary'].split(',')[0:7]
        if title[0] == "Sunday" \
                or today == "Sunday" and title == "Today":
            sunday_weather = item['summary'].split(',')[0:7]

    # ----------------------------------------------------------- #
    # Render the page
    # ----------------------------------------------------------- #

    if private_gpx:
        flash("One or more routes hasn't been made public yet!")

    return render_template("weekend.html", year=current_year,
                           GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY, ELSR_HOME=ELSR_HOME, MAP_BOUNDS=MAP_BOUNDS,
                           saturday=saturday, saturday_rides=saturday_rides, saturday_cafes=saturday_cafes_elevations,
                           saturday_polylines=saturday_polylines, saturday_elevation_data=saturday_elevation_data,
                           saturday_elevation_cafes=saturday_elevation_cafes, saturday_weather=saturday_weather,
                           sunday=sunday, sunday_rides=sunday_rides, sunday_cafes=sunday_cafes_elevations,
                           sunday_polylines=sunday_polylines, sunday_elevation_data=sunday_elevation_data,
                           sunday_elevation_cafes=sunday_elevation_cafes, sunday_weather=sunday_weather,
                           saturday_date=saturday_date, sunday_date=sunday_date)


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
    # Validate ride_id
    # ----------------------------------------------------------- #
    if ride_id:
        ride = Calendar().one_ride_id(ride_id)
        if not ride:
            app.logger.debug(f"add_ride(): Failed to locate ride, ride_id = '{ride_id}'.")
            Event().log_event("Edit Ride Fail", f"Failed to locate ride, ride_id = '{ride_id}'.")
            return abort(404)

    # ----------------------------------------------------------- #
    # Need the form
    # ----------------------------------------------------------- #
    if ride_id:
        # ----------------------------------------------------------- #
        # Edit event, so pre-fill form from dB
        # ----------------------------------------------------------- #
        gpx = Gpx().one_gpx(ride.gpx_id)
        cafe = Cafe().one_cafe(ride.cafe_id)
        # These are the easy ones
        form = CreateRideForm(
            date=datetime.strptime(ride.date.strip(), '%d%m%Y'),
            leader=ride.leader,
            group=ride.group,
            gpx_name=f"{gpx.id}: '{gpx.name}', {gpx.length_km}km / {gpx.ascent_m}m",
        )
        # Cafe might not be in the dB yet, so handle exception
        if cafe:
            form.destination.data = f"{cafe.name} ({cafe.id})"
            form.new_destination.data = ""
        else:
            form.destination.data = NEW_CAFE
            form.new_destination.data = ride.destination
    else:
        # ----------------------------------------------------------- #
        # Add event, so start with fresh form
        # ----------------------------------------------------------- #
        form = CreateRideForm()

        # Pre-populate the data in the form, if we were passed one
        if start_date_str:
            start_date = datetime(int(start_date_str[4:8]), int(start_date_str[2:4]), int(start_date_str[0:2]), 0, 00)
            form.date.data = start_date

        # Assume the author is the group leader
        if not form.leader.data:
            form.leader.data = current_user.name

    # Are we posting the completed comment form?
    if form.validate_on_submit():
        # ----------------------------------------------------------- #
        # Handle form passing validation
        # ----------------------------------------------------------- #

        # 1: Validate date (must be in the future)
        formdate = form.date.data
        today = datetime.today()
        if formdate < today:
            flash("The date is in the past!")
            return render_template("add_ride_to_calendar.html", year=current_year, form=form)

        # 2: Validate cafe (must be specified)
        if form.destination.data == NEW_CAFE \
                and form.new_destination.data == "":
            flash("New cafe not specified!")
            return render_template("add_ride_to_calendar.html", year=current_year, form=form)

        # 3: Check we can find cafe in the dB
        if form.destination.data != NEW_CAFE:
            # Work out which cafe they selected in the drop down
            # eg "Goat and Grass (was curious goat) (46)"
            cafe_id = form.destination.data.split('(')[-1].split(')')[0]
            cafe = Cafe().one_cafe(cafe_id)
            if not cafe:
                # Should never happen, but....
                app.logger.debug(f"add_ride(): Failed to get cafe from '{form.destination.data}'.")
                Event().log_event("Add ride Fail", f"Failed to get cafe from '{form.destination.data}'.")
                flash("Sorry, something went wrong - couldn't understand the cafe choice.")
                return render_template("add_ride_to_calendar.html", year=current_year, form=form)
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
            gpx_id = form.gpx_name.data.split(':')[0]
            gpx = Gpx().one_gpx(gpx_id)
            if not gpx:
                # Should never happen, but....
                app.logger.debug(f"add_ride(): Failed to get GPX from '{form.gpx_name.data}'.")
                Event().log_event("Add ride Fail", f"Failed to get GPX from '{form.gpx_name.data}'.")
                flash("Sorry, something went wrong - couldn't understand the GPX choice.")
                return render_template("add_ride_to_calendar.html", year=current_year, form=form)
        else:
            # They are uploading their own GPX file
            gpx = None

        # 6: Check route passes cafe (if both from comboboxes)
        if gpx and cafe:
            match = False
            for cafe_passed in json.loads(gpx.cafes_passed):
                if int(cafe_passed["cafe_id"]) == cafe.id:
                    match = True
            if not match:
                flash(f"That GPX route doesn't pass {cafe.name}!")
                return render_template("add_ride_to_calendar.html", year=current_year, form=form)

        # 7: Check they aren't nominating someone else (only Admin can nominate another person)
        if not current_user.admin():
            # Allow them to append eg "Simon" -> "Simon Bond"
            if form.leader.data[0:len(current_user.name)] != current_user.name:
                # Looks like they've nominated someone else
                flash("Only Admins can nominate someone else to lead a ride.")
                # In case they've forgotten their user name
                form.leader.data = current_user.name
                return render_template("add_ride_to_calendar.html", year=current_year, form=form)

        # ----------------------------------------------------------- #
        # Do we need to upload a GPX?
        # ----------------------------------------------------------- #




        # ----------------------------------------------------------- #
        # We can now add / update the event
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
        if cafe:
            new_ride.destination = cafe.name
            new_ride.cafe_id = cafe.id
        else:
            new_ride.destination = form.new_destination.data
            new_ride.cafe_id = None
        new_ride.group = form.group.data
        new_ride.gpx_id = gpx.id

        # Add to the dB
        if Calendar().add_ride(new_ride):
            # Success
            app.logger.debug(f"add_ride(): Successfully added new ride.")
            Event().log_event("Add ride Pass", f"Successfully added new_ride.")
            if ride:
                flash("Ride updated!")
            else:
                flash("Ride added to Calendar!")
            # Go to Calendar page for this ride's date
            return redirect(url_for('weekend', date=start_date_str))
        else:
            # Should never happen, but...
            app.logger.debug(f"add_ride(): Failed to add ride from '{new_ride}'.")
            Event().log_event("Add ride Fail", f"Failed to add ride '{new_ride}'.")
            flash("Sorry, something went wrong.")
            return render_template("add_ride_to_calendar.html", year=current_year, form=form)

    # ----------------------------------------------------------- #
    # Handle POST
    # ----------------------------------------------------------- #

    elif request.method == 'POST':

        # This traps a post, but where the form verification failed.
        flash("Something was missing, see comments below:")
        return render_template("add_ride_to_calendar.html", year=current_year, form=form)

    # ----------------------------------------------------------- #
    # Handle GET
    # ----------------------------------------------------------- #

    return render_template("add_ride_to_calendar.html", year=current_year, form=form)


# -------------------------------------------------------------------------------------------------------------- #
# Delete a comment
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
            and current_user.email != ride.email:
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
