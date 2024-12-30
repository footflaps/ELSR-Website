from flask import render_template, url_for, flash, abort
from datetime import datetime, date
import calendar as cal
from dateutil.relativedelta import relativedelta


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.calendar_repository import CalendarRepository, GROUP_CHOICES
from core.database.repositories.social_repository import SocialRepository
from core.database.repositories.blog_repository import BlogRepository
from core.database.repositories.gpx_repository import GpxRepository
from core.subs_google_maps import create_polyline_set, MAX_NUM_GPX_PER_GRAPH, MAP_BOUNDS, \
                                  google_maps_api_key, count_map_loads
from core.database.repositories.cafe_repository import CafeRepository, OPEN_CAFE_COLOUR, CLOSED_CAFE_COLOUR
from core.subs_dates import get_date_from_url

from core.decorators.user_decorators import update_last_seen, logout_barred_user


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# How much calendar we populate relative to the focus date
LOOK_BACK_MONTHS = 3
LOOK_FORWARD_MONTHS = 6


# ELSR Chaingang details
CHAINGANG_DAY = "Thursday"
# From last week of March
CHAINGANG_START_DATE = datetime(2024, 3, 28, 0, 00)
# To last week of September
CHAINGANG_END_DATE = datetime(2024, 9, 19, 0, 00)

# Tim's Turbo Sessions (TTS) details
TTS_DAY = "Tuesday"
# From November 2024
TTS_START_DATE = datetime(2024, 11, 12, 0, 00)
# To late March 2025
TTS_END_DATE = datetime(2025, 3, 20, 0, 00)


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def get_calendar_start_month_year(target_date_str: str):
    # Just use today's date for how we launch the calendar
    start_year = datetime.today().year
    start_month = datetime.today().month

    if target_date_str:
        try:
            try_year = int(target_date_str[4:8])
            try_month = int(target_date_str[2:4])
        except Exception:
            # If we get garbage, just use today
            flash(f"Invalid date string '{target_date_str}', was expecting 'DDMMYYYY'.")
            try_year = -1
            try_month = -1

        # Better check it is a real date and not just random numbers
        if 1 <= try_month <= 12 \
                and start_year - 1 <= try_year <= start_year + 1:
            start_year = try_year
            start_month = try_month

    return start_month, start_year


def get_date_range_look_around(date_str: str, look_back_months: int, look_forward_months: int):
    """
    Calculate dates `LOOK_BACK_MONTHS` ago and `LOOK_FORWARD_MONTHS` ahead.

    :param date_str:                            The date in the format 'DDMMYY'.
    :param look_back_months:                    Number of months to look back.
    :param look_forward_months:                 Number of months to look forward.
    :return:                                    A tuple of two dates (look_back_date, look_forward_date) in 'DDMMYY' format.
    """
    try:
        # Convert the input date from 'DDMMYY' format to a datetime object
        input_date = datetime.strptime(date_str, "%d%m%y")

        # Calculate the dates
        look_back_date = input_date - relativedelta(months=look_back_months)
        look_forward_date = input_date + relativedelta(months=look_forward_months)

        # Convert the calculated dates back to 'DDMMYY' format
        look_back_date_str = look_back_date.strftime("%Y-%m-%d")
        look_forward_date_str = look_forward_date.strftime("%Y-%m-%d")

        return look_back_date_str, look_forward_date_str

    except ValueError as e:
        raise ValueError(f"Invalid date format: '{date_str}'. Expected format is 'DDMMYY'.") from e


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Show the Calendar
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/calendar', methods=['GET'])
@logout_barred_user
@update_last_seen
def calendar():
    # ----------------------------------------------------------- #
    # Did we get passed a date? (Optional)
    # ----------------------------------------------------------- #
    target_date_str = get_date_from_url(return_none_if_empty=True)

    # ----------------------------------------------------------- #
    # Work out year and month, to focus calendar
    # ----------------------------------------------------------- #
    focus_month, focus_year = get_calendar_start_month_year(target_date_str)
    print(f"focus_month: {focus_month}, focus_year: {focus_year}")

    # ----------------------------------------------------------- #
    # Get Start and Finish Dates for populating calendar
    # ----------------------------------------------------------- #

    start_date_str, end_date_str = get_date_range_look_around(date_str=f"01{focus_month}{str(focus_year)[2:4]}", look_back_months=LOOK_BACK_MONTHS,
                                                             look_forward_months=LOOK_FORWARD_MONTHS)
    print(f"start_date_str: {start_date_str}, end_date_str: {end_date_str}")

    # ----------------------------------------------------------- #
    # Create calendar events for the calendar JS module
    # ----------------------------------------------------------- #
    js_calendar_events = []
    unique_ride_dates = set()

    # ----------------------------------------------------------- #
    # Get all calendar, blog and social events over this period
    # ----------------------------------------------------------- #
    ride_events = CalendarRepository().all_by_date_range(start_date_str, end_date_str)
    print(f"We got {len(ride_events)} calendar events")

    blog_events = BlogRepository().all_by_date_range(start_date_str, end_date_str)
    print(f"We got {len(blog_events)} blog events")

    social_events = SocialRepository().all_by_date_range(start_date_str, end_date_str)
    print(f"We got {len(social_events)} social events")

    # Highlight today in the calendar
    today_str = datetime.today().strftime("%Y-%m-%d")

    # ----------------------------------------------------------- #
    # Loop over interval day by day
    # ----------------------------------------------------------- #
    # JS Calendar module can only accept one event per day, so we have to
    # combine all our different events into a single entry.
    year = focus_year
    month = focus_month - LOOK_BACK_MONTHS
    for _ in range(0, LOOK_BACK_MONTHS + LOOK_FORWARD_MONTHS):

        # Handle month wrapping
        if month == 13:
            year += 1
            month = 1
        elif month <= 0:
            year -= 1
            month = 12 + month

        # Loop over days in the month
        for day in range(1, cal.monthrange(year, month)[1] + 1):
            day_datestr = datetime(year, month, day, 0, 00)
            day_of_week = day_datestr.strftime("%A")

            datestr = f"{format(day, '02d')}{format(month, '02d')}{year}"
            markup = ""

            # ----------------------------------------------------------- #
            # Add Rides
            # ----------------------------------------------------------- #
            for event in ride_events:
                if event.converted_date == date(year, month, day):
                    # Just create one link to calendar for that date, which will show all rides
                    if event.converted_date not in unique_ride_dates:
                        unique_ride_dates.add(event.converted_date)

                        # Extract the year, month, and day from the converted_date
                        year = event.converted_date.year
                        month = event.converted_date.month
                        day = event.converted_date.day

                        # Create Marker
                        markup = f"<a href='{url_for('weekend', date=f'{datestr}')}'>" \
                                 f"<i class='fas fa-solid fa-person-biking fa-2xl'></i></a>"

            # ----------------------------------------------------------- #
            # Add Socials
            # ----------------------------------------------------------- #
            for event in social_events:
                if event.converted_date == date(year, month, day):
                    # Extract the year, month, and day from the converted_date
                    year = event.converted_date.year
                    month = event.converted_date.month
                    day = event.converted_date.day

                    # Create Marker
                    markup += f"<a href='{url_for('social', date=f'{datestr}')}'>" \
                              f"<i class='fas fa-solid fa-champagne-glasses fa-2xl'></i></a>"

            # ----------------------------------------------------------- #
            # Add Blogs
            # ----------------------------------------------------------- #
            for event in blog_events:
                if event.converted_date == date(year, month, day):
                    # Extract the year, month, and day from the converted_date
                    year = event.converted_date.year
                    month = event.converted_date.month
                    day = event.converted_date.day

                    # Create Marker
                    markup += f"<a href='{url_for('display_blog', blog_id=f'{event.id}')}'>" \
                              f"<i class='fas fa-solid fa-flag-checkered fa-xl'></i></a>"

            # ----------------------------------------------------------- #
            # Add Chaingangs
            # ----------------------------------------------------------- #
            if day_of_week == CHAINGANG_DAY:
                if CHAINGANG_START_DATE <= day_datestr <= CHAINGANG_END_DATE:
                    markup += f"<a href='{url_for('chaingang')}'>" \
                              f"<i class='fas fa-solid fa-arrows-spin fa-spin fa-xl'></i></a>"

            # ----------------------------------------------------------- #
            # Add TTS
            # ----------------------------------------------------------- #
            if day_of_week == TTS_DAY:
                if TTS_START_DATE <= day_datestr <= TTS_END_DATE:
                    markup += f"<a href='{url_for('turbo_training')}'>" \
                              f"<i class='fa-solid fa-users-rectangle fa-lg'></i></a>&nbsp"

            # ----------------------------------------------------------- #
            # Add TWRs
            # ----------------------------------------------------------- #
            if day_of_week == "Wednesday" \
                    and date(year, month, day) not in unique_ride_dates:
                markup += f"<a href='{url_for('twr')}'>" \
                          f"<i class='fas fa-solid fa-person-biking fa-xl'></i></a>&nbsp"

            # ----------------------------------------------------------- #
            # Add today
            # ----------------------------------------------------------- #
            if f"{year}-{format(month, '02d')}-{format(day, '02d')}" == today_str:
                markup += '<span class="badge bg-primary">[day]</span>'

            # ----------------------------------------------------------- #
            # Add single entry for the day
            # ----------------------------------------------------------- #
            if markup != "":
                js_calendar_events.append({
                    "date": f"{year}-{format(month, '02d')}-{format(day, '02d')}",
                    "markup": markup
                })

        # Next month
        month += 1

    return render_template("calendar.html", year=current_year, events=js_calendar_events, live_site=live_site(),
                           start_month=focus_month, start_year=focus_year)


# -------------------------------------------------------------------------------------------------------------- #
# Group ride history
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/ride_history/<request>', methods=['GET'])
@logout_barred_user
@update_last_seen
def ride_history(request):
    # ----------------------------------------------------------- #
    # Sort out which group we are
    # ----------------------------------------------------------- #
    # GROUP_CHOICES = ["Decaff", "Espresso", "Doppio", "Mixed"]
    group = None
    for option in GROUP_CHOICES:
        if request.lower() == option.lower():
            group = option
            break

    if not group:
        flash(f"Sorry, unknown group '{group}'!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Extract all the rides from the calendar
    # ----------------------------------------------------------- #
    rides = CalendarRepository().all_calender_group_in_past(group)

    # ----------------------------------------------------------- #
    # Extract details from the GPX and add to the ride objects
    # ----------------------------------------------------------- #
    # We need a set of GPX files later on
    gpxes = []
    # We need a set of cafe markers for the map
    cafe_markers = []

    for ride in rides:
        gpx_id = ride.gpx_id
        gpx = GpxRepository().one_gpx(gpx_id)
        if gpx:
            gpxes.append(gpx)
            ride.length_km = gpx.length_km
            ride.ascent_m = gpx.ascent_m

            # Also add marker for the cafe (but only if we're showing the GPX)
            cafe_id = ride.cafe_id
            cafe = CafeRepository().one_cafe(cafe_id)
            if cafe:
                if len(gpxes) <= MAX_NUM_GPX_PER_GRAPH:
                    if cafe.active:
                        cafe_colour = OPEN_CAFE_COLOUR
                    else:
                        cafe_colour = CLOSED_CAFE_COLOUR
                    cafe_markers.append({
                        "position": {"lat": cafe.lat, "lng": cafe.lon},
                        "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
                        "color": cafe_colour,
                    })
        else:
            ride.length_km = "n/a"
            ride.ascent_m = "n/a"

    # ----------------------------------------------------------- #
    # Map for the possible routes
    # ----------------------------------------------------------- #
    # NB create_polyline_set enforces MAX_NUM_GPX_PER_GRAPH
    polylines = create_polyline_set(gpxes)

    # Warn if we skipped any
    if len(gpxes) >= MAX_NUM_GPX_PER_GRAPH:
        warning = f"NB: Only showing first {MAX_NUM_GPX_PER_GRAPH} routes on map."
    else:
        warning = None

    # ----------------------------------------------------------- #
    # Add to map counts
    # ----------------------------------------------------------- #
    if polylines['polylines']:
        count_map_loads(1)

    # ----------------------------------------------------------- #
    # Render the page
    # ----------------------------------------------------------- #
    return render_template("calendar_group.html", year=current_year, group_name=group, rides=rides,
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), warning=warning,
                           MAP_BOUNDS=MAP_BOUNDS, gpxes=gpxes, cafes=cafe_markers, live_site=live_site(),
                           polylines=polylines['polylines'], midlat=polylines['midlat'], midlon=polylines['midlon'])
