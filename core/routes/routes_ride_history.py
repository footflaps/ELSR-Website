from flask import render_template, url_for, flash, abort, Response


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.calendar_repository import CalendarRepository, GROUP_CHOICES
from core.database.repositories.gpx_repository import GpxRepository
from core.database.repositories.cafe_repository import CafeRepository, OPEN_CAFE_COLOUR, CLOSED_CAFE_COLOUR

from core.subs_google_maps import create_polyline_set, MAX_NUM_GPX_PER_GRAPH, MAP_BOUNDS, \
                                  google_maps_api_key, count_map_loads

from core.decorators.user_decorators import update_last_seen, logout_barred_user


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Group ride history
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/ride_history/<request>', methods=['GET'])
@logout_barred_user
@update_last_seen
def ride_history(request) -> Response | str:
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
        gpx = GpxRepository().one_by_id(gpx_id)
        if gpx:
            gpxes.append(gpx)
            ride.length_km = gpx.length_km
            ride.ascent_m = gpx.ascent_m

            # Also add marker for the cafe (but only if we're showing the GPX)
            cafe_id = ride.cafe_id
            cafe = CafeRepository().one_by_id(cafe_id)
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
