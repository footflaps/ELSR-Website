from flask import render_template, url_for
from bbc_feeds import weather
from datetime import datetime as date

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
from core.db_users import User, update_last_seen
from core.subs_graphjs import get_elevation_data_set, get_destination_cafe_height

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
def calendar():
    # -------------------------------------------------------------------------------------------- #
    # Show the schedule of rides
    # -------------------------------------------------------------------------------------------- #

    saturday = "Saturday Aug 19 2023"
    sunday = "Sunday Aug 20 2023"

    saturday_rides = [
        {"group": "Decaff",
         "leader": "Anna",
         "destination": "Buntingford",
         "distance": 96,
         "elevation": 672,
         "gpx_id": 1,

         },
        {"group": "Espresso",
         "leader": "Andy Linney",
         "destination": "Mill End",
         "distance": 105,
         "elevation": 803,
         "gpx_id": 2,
         },
        {"group": "Doppio",
         "leader": "Andy Fry",
         "destination": "The Cow Shed",
         "distance": 110,
         "elevation": 750,
         "gpx_id": 3,
         }]

    sunday_rides = [
        {"group": "Mixed",
         "leader": "Ian",
         "destination": "La Hogue",
         "distance": 89,
         "elevation": 551,
         "gpx_id": 12,
         }]

    # ----------------------------------------------------------- #
    # Polylines for the GPX files
    # ----------------------------------------------------------- #
    saturday_gpxes = [Gpx().one_gpx(1), Gpx().one_gpx(2), Gpx().one_gpx(3)]
    saturday_polylines = create_polyline_set(saturday_gpxes)

    sunday_gpxes = [Gpx().one_gpx(12)]
    sunday_polylines = create_polyline_set(sunday_gpxes)

    # ----------------------------------------------------------- #
    # Dataset for the destination cafes
    # ----------------------------------------------------------- #
    sat_cafes = [Cafe().one_cafe(5), Cafe().one_cafe(39), Cafe().one_cafe(8)]

    saturday_cafes = []
    for cafe in sat_cafes:
        saturday_cafes.append({
            "position": {"lat": cafe.lat, "lng": cafe.lon},
            "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
            "color": OPEN_CAFE_COLOUR,
        })

    sun_cafes = [Cafe().one_cafe(41)]

    sunday_cafes = []
    for cafe in sun_cafes:
        sunday_cafes.append({
            "position": {"lat": cafe.lat, "lng": cafe.lon},
            "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
            "color": OPEN_CAFE_COLOUR,
        })

    # ----------------------------------------------------------- #
    # Get elevation data
    # ----------------------------------------------------------- #

    # Elevation traces
    saturday_elevation_data = get_elevation_data_set(saturday_gpxes)
    sunday_elevation_data = get_elevation_data_set(sunday_gpxes)

    # Cafes for elevation graphs
    saturday_elevation_cafes = get_destination_cafe_height(saturday_elevation_data, saturday_gpxes, sat_cafes)
    sunday_elevation_cafes = get_destination_cafe_height(sunday_elevation_data, sunday_gpxes, sun_cafes)

    # ----------------------------------------------------------- #
    # Get weather
    # ----------------------------------------------------------- #
    bbc_weather = weather().forecast(CAMBRIDGE_BBC_WEATHER_CODE)
    saturday_weather = None
    sunday_weather = None
    today = date.today().strftime("%A")
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
    return render_template("weekend.html", year=current_year,
                           GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY, ELSR_HOME=ELSR_HOME, MAP_BOUNDS=MAP_BOUNDS,
                           saturday=saturday, saturday_rides=saturday_rides, saturday_cafes=saturday_cafes,
                           saturday_polylines=saturday_polylines, saturday_elevation_data=saturday_elevation_data,
                           saturday_elevation_cafes=saturday_elevation_cafes, saturday_weather=saturday_weather,
                           sunday=sunday, sunday_rides=sunday_rides, sunday_cafes=sunday_cafes,
                           sunday_polylines=sunday_polylines, sunday_elevation_data=sunday_elevation_data,
                           sunday_elevation_cafes=sunday_elevation_cafes, sunday_weather=sunday_weather)
