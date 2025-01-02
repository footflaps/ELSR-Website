from flask import render_template, url_for, flash, abort, Response
from bbc_feeds import weather
from datetime import datetime, timedelta
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site, GLOBAL_FLASH

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.cafe_repository import CafeModel, CafeRepository, OPEN_CAFE_COLOUR, CLOSED_CAFE_COLOUR
from core.database.repositories.gpx_repository import GpxModel, GpxRepository
from core.database.repositories.calendar_repository import CalendarModel, CalendarRepository, DEFAULT_START_TIMES
from core.database.repositories.event_repository import EventRepository

from core.database.jinja.calendar_jinja import start_time_string

from core.decorators.user_decorators import update_last_seen, logout_barred_user

from core.subs_google_maps import create_polyline_set, ELSR_HOME, MAP_BOUNDS, google_maps_api_key, count_map_loads
from core.subs_gpx import GPX_UPLOAD_FOLDER_ABS
from core.subs_graphjs import get_elevation_data_set, get_destination_cafe_height
from core.subs_dates import get_date_from_url


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

CAMBRIDGE_BBC_WEATHER_CODE = 2653941


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Work out which days we will display
# -------------------------------------------------------------------------------------------------------------- #
def work_out_days(target_date_str) -> list[object] | None:
    """
    The weekend page displays all the rides for the upcoming weekend. However, we may have been called with a date
    for a weekend further in the future or in the past. The weekend may also be a BH (with a Friday, Monday or both
    tagged on). If it is a BH Weekend, then we will also include the BH days in the WE page, but only if we have rides
    scheduled on the BH days. So this function works out the set of dates which we will display in the WE page. NB It
    doesn't actually check for official Bank Holidays, it just looks for rides scheduled on the Friday or Monday. If
    the function is called with a mid-week day, eg a random Wednesday, it will just return the date for that day.

    :param target_date_str:                     The date string requested in format "DDMMYYYY"
    :return:
    """
    # Step 1: Create a set of date strings eg ["23082023", "24082023" ]
    if target_date_str:
        # ----------------------------------------------------------- #
        # Scenario #1 - Passed a specific date, so find that day
        # ----------------------------------------------------------- #
        # NB We may have been parsed garbage as the date
        try:
            target_date = datetime(int(target_date_str[4:8]),
                                   int(target_date_str[2:4]),
                                   int(target_date_str[0:2]),
                                   0, 00)
        except Exception:
            # Flag back fail
            return None

        # Get the day of week
        day_str: str = target_date.strftime("%A")

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
                "Sunday": target_date.strftime("%d%m%Y")
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
                "Sunday": (today + timedelta(days=1)).strftime("%d%m%Y")
            }

        elif today_str == "Sunday":
            # Yesterday and today
            dates_short = {
                "Saturday": (today - timedelta(days=1)).strftime("%d%m%Y"),
                "Sunday": today.strftime("%d%m%Y")
            }

        else:
            # Next weekend
            saturday = today + timedelta((5 - today.weekday()) % 7)
            dates_short = {
                "Saturday": saturday.strftime("%d%m%Y"),
                "Sunday": (saturday + timedelta(days=1)).strftime("%d%m%Y")
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
        if CalendarRepository().all_calendar_date(friday_date_str):
            # We have a ride on the Friday, so pre-pend Friday
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
        if CalendarRepository().all_calendar_date(monday_date_str):
            # We have a ride on the Monday, so append Monday
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
    dates_long: dict[str, str] = {}

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
@logout_barred_user
@update_last_seen
def weekend() -> Response | str:
    # ----------------------------------------------------------- #
    # Did we get passed a date? (Optional)
    # ----------------------------------------------------------- #
    target_date_str: str | None = get_date_from_url(return_none_if_empty=True)

    # ----------------------------------------------------------- #
    # Workout which weekend we're displaying
    # ----------------------------------------------------------- #
    tmp: list | None = work_out_days(target_date_str)

    # The above returns None if the date was garbage
    if not tmp:
        # Fed invalid date
        app.logger.debug(f"weekend(): Failed to understand target_date_str = '{target_date_str}'.")
        EventRepository().log_event("Weekend Fail", f"Failed to understand target_date_str = '{target_date_str}'.")
        return abort(404)
    else:
        # Get what we actually wanted from work_out_days()
        days = tmp[0]  # eg 'Saturday'
        dates_long = tmp[1]  # eg 'Saturday 25 August 2023'
        dates_short = tmp[2]  # eg '01022023'

    # ----------------------------------------------------------- #
    # Add GPX details
    # ----------------------------------------------------------- #

    # We will populate these dictionaries for each day
    rides: dict = {}
    gpxes: dict = {}
    cafe_coords: dict = {}
    cafes: dict = {}
    start_details: dict = {}

    # We will flash a warning if we find a private GPX in any of the weekend's routes
    private_gpx: bool = False

    # Populate everything for each day eg loop over ['Saturday', 'Sunday']
    for day in days:
        # Get a set of rides for this day from the calendar indexed by short dates eg '01022024'
        tmp_rides: list[CalendarModel] = CalendarRepository().all_calendar_date(dates_short[day])

        # Create empty sets for all the data jinja will need to populate each day
        rides[day] = []
        gpxes[day] = []
        cafes[day] = []
        start_details[day] = []
        cafe_coords[day] = []

        # Loop over each ride
        for ride in tmp_rides:
            # Look up the GPX object referenced in the ride object
            gpx: GpxModel | None = GpxRepository().one_by_id(ride.gpx_id)

            # NB It could have been deleted, so check it still exists
            if gpx:
                # Extract ride stats which are cached in the GPX object (no need to read the actual file)
                ride.distance = gpx.length_km
                ride.elevation = gpx.ascent_m
                ride.public = gpx.public

                # Make a note of any non-standard start times
                # NB start_time should always be set, but you never know...
                if ride.start_time:
                    # NB treat a blank entry as normal start time for that day
                    if ride.start_time.strip() != "":
                        if ride.start_time.strip() != start_time_string(DEFAULT_START_TIMES[day]):
                            # start_details[day].append(f"{ride.destination}: {ride.start_time}")
                            start_details[day].append({'group': ride.group,
                                                       'destination': ride.destination,
                                                       'start_time': ride.start_time,
                                                       })

                # Make a note, if we find a non-public GPX as this will stop people downloading the file
                if not gpx.public:
                    private_gpx = True

                # Add gpx object to the list of GPX files for this day
                gpxes[day].append(gpx)

                # Add ride to the list of rides this day
                rides[day].append(ride)

                # Look up cafe (which might not yet be in the db)
                cafe: CafeModel | None = CafeRepository().one_by_id(ride.cafe_id)
                if cafe:
                    # Update destination (as cafe may have changed name)
                    ride.destination = cafe.name

                    # Create a marker for Google Maps for this cafe
                    if cafe.active:
                        color: str = OPEN_CAFE_COLOUR
                    else:
                        flash(f"Cafe '{cafe.name}' has been flagged as Closed!")
                        color = CLOSED_CAFE_COLOUR
                    cafe_coords[day].append({
                        "position": {"lat": cafe.lat, "lng": cafe.lon},
                        "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
                        "color": color,
                    })
                    cafes[day].append(cafe)
                else:
                    # Just add a blank cafe object
                    cafes[day].append(CafeRepository())

                # Double check we can find the GPX file
                # NB have seen once where it was stuck as a tmp file - wonder if I updated the website mid edit?
                filename: str = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
                if os.path.exists(filename):
                    ride.missing_gpx = False
                else:
                    # Flag missing GPX file (will only be shown to Admins)
                    ride.missing_gpx = True
                    app.logger.debug(f"weekend(): Failed to locate GPX file, ride_id = '{ride.id}'.")
                    EventRepository().log_event("Weekend Fail", f"Failed to locate GPX file, ride_id = '{ride.id}'.")
                    flash(
                        f"Looks like GPX file for ride '{ride.destination}' "
                        f"(ride.id = {ride.id}, leader = '{ride.leader}') has been deleted!")

            else:
                # Missing GPX row in the table
                app.logger.debug(f"weekend(): Failed to locate GPX entry, ride_id = '{ride.id}'.")
                EventRepository().log_event("Weekend Fail", f"Failed to locate GPX entry, ride_id = '{ride.id}'.")
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
            # Weather is titled 'Saturday', 'Sunday', etc or 'Today' - so we have to figure out what 'Today' is...
            if title[0] == day \
                    or today == day and title == "Today":
                weather_data[day] = item['summary'].split(',')[0:7]

    # ----------------------------------------------------------- #
    # Render the page
    # ----------------------------------------------------------- #
    if private_gpx:
        flash("One or more routes hasn't been made public yet!")

    # Temporary alert for change of meeting point
    if GLOBAL_FLASH:
        flash(GLOBAL_FLASH)

    # Render the page
    return render_template("calendar_weekend.html", year=current_year,
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), ELSR_HOME=ELSR_HOME, MAP_BOUNDS=MAP_BOUNDS,
                           days=days, dates_long=dates_long, dates_short=dates_short,
                           DEFAULT_START_TIMES=DEFAULT_START_TIMES,
                           rides=rides, start_details=start_details, weather_data=weather_data,
                           polylines=polylines, cafe_coords=cafe_coords, live_site=live_site(),
                           elevation_data=elevation_data, elevation_cafes=elevation_cafes, anchor=target_date_str)
