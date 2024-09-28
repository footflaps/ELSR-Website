from flask import render_template, url_for, flash, abort
from datetime import datetime
import calendar as cal


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import update_last_seen, logout_barred_user
from core.db_calendar import Calendar, GROUP_CHOICES
from core.db_social import Socials
from core.db_blog import Blog
from core.dB_gpx import Gpx
from core.subs_google_maps import create_polyline_set, MAX_NUM_GPX_PER_GRAPH, MAP_BOUNDS, \
                                  google_maps_api_key, count_map_loads
from core.dB_cafes import Cafe, OPEN_CAFE_COLOUR, CLOSED_CAFE_COLOUR
from core.subs_photos import get_date_from_url


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# ELSR Chaingang details
CHAINGANG_DAY = "Thursday"
# From last week of March
CHAINGANG_START_DATE = datetime(2024, 3, 28, 0, 00)
# To last week of September
CHAINGANG_END_DATE = datetime(2024, 9, 19, 0, 00)

# Tim's Turbo Sessions (TTS) details
TTS_DAY = "Tuesday"
# From October 2023
TTS_START_DATE = datetime(2023, 10, 10, 0, 00)
# To late march 2024
TTS_END_DATE = datetime(2024, 3, 19, 0, 00)


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
    # Work out year and month, to pre-load calendar
    # ----------------------------------------------------------- #
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

    # ----------------------------------------------------------- #
    # Need to build a list of events
    # ----------------------------------------------------------- #
    events = []

    # ----------------------------------------------------------- #
    # Loop over time
    # ----------------------------------------------------------- #
    year = datetime.today().year
    # Start three months behind to backfill calendar a bit
    month = datetime.today().month - 3
    today_str = datetime.today().strftime("%Y-%m-%d")
    # Just cover 9 month span
    for _ in range(0, 9):
        if month == 13:
            year += 1
            month = 1
        elif month <= 0:
            year -= 1
            month = 12 + month
        for day in range(1, cal.monthrange(year, month)[1] + 1):
            day_datestr = datetime(year, month, day, 0, 00)
            day_of_week = day_datestr.strftime("%A")
            datestr = f"{format(day, '02d')}{format(month, '02d')}{year}"

            markup = ""
            added_ride = False

            # ----------------------------------------------------------- #
            # Request rides from Calendar class
            # ----------------------------------------------------------- #
            if Calendar().all_calendar_date(datestr):
                markup += f"<a href='{url_for('weekend', date=f'{datestr}')}'>" \
                          f"<i class='fas fa-solid fa-person-biking fa-2xl'></i></a>"
                added_ride = True

            # ----------------------------------------------------------- #
            # Request socials from Socials class
            # ----------------------------------------------------------- #
            if Socials().all_socials_date(datestr):
                markup += f"<a href='{url_for('social', date=f'{datestr}')}'>" \
                          f"<i class='fas fa-solid fa-champagne-glasses fa-2xl'></i></a>"

            # ----------------------------------------------------------- #
            # Request events from Blog class
            # ----------------------------------------------------------- #
            for event in Blog().all_by_date(datestr):
                markup += f"<a href='{url_for('blog', blog_id=f'{event.id}')}'>" \
                          f"<i class='fas fa-solid fa-flag-checkered fa-xl'></i></a>"

            # ----------------------------------------------------------- #
            # Add chaingangs
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
                    and not added_ride:
                markup += f"<a href='{url_for('twr')}'>" \
                          f"<i class='fas fa-solid fa-person-biking fa-xl'></i></a>&nbsp"

            # ----------------------------------------------------------- #
            # Add today
            # ----------------------------------------------------------- #
            if f"{year}-{format(month, '02d')}-{format(day, '02d')}" == today_str:
                markup += '<span class="badge bg-primary">[day]</span>'
            else:
                markup += "[day]"

            # ----------------------------------------------------------- #
            # Add single entry for the day
            # ----------------------------------------------------------- #
            if markup != "":
                events.append({
                    "date": f"{year}-{format(month, '02d')}-{format(day, '02d')}",
                    "markup": markup
                })

        # Next month
        month += 1

    return render_template("calendar.html", year=current_year, events=events, live_site=live_site(),
                           start_month=start_month, start_year=start_year)


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
    rides = Calendar().all_calender_group_in_past(group)

    # ----------------------------------------------------------- #
    # Extract details from the GPX and add to the ride objects
    # ----------------------------------------------------------- #
    # We need a set of GPX files later on
    gpxes = []
    # We need a set of cafe markers for the map
    cafe_markers = []

    for ride in rides:
        gpx_id = ride.gpx_id
        gpx = Gpx().one_gpx(gpx_id)
        if gpx:
            gpxes.append(gpx)
            ride.length_km = gpx.length_km
            ride.ascent_m = gpx.ascent_m

            # Also add marker for the cafe (but only if we're showing the GPX)
            cafe_id = ride.cafe_id
            cafe = Cafe().one_cafe(cafe_id)
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
