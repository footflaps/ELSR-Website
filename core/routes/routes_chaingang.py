from flask import render_template, request, flash, abort
import os
import requests as requests2
from bs4 import BeautifulSoup


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, GPX_UPLOAD_FOLDER_ABS, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our Decorators
# -------------------------------------------------------------------------------------------------------------- #

from core.decorators.user_decorators import update_last_seen


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.cafe_repository import OPEN_CAFE_COLOUR
from core.subs_graphjs import get_elevation_data
from core.subs_google_maps import polyline_json, google_maps_api_key, MAP_BOUNDS, count_map_loads
from core.database.repositories.event_repository import EventRepository
from core.database.jinja.message_jinja import admin_has_mail


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

CHAINGANG_GPX_FILENAME = "gpx_el_cg_2023.gpx"

CHAINGANG_MEET_NEW = [{
    "position": {"lat": 52.22528, "lng": 0.043116},
    "title": f'<a href="https://threehorseshoesmadingley.co.uk/">Three Horseshoes</a>',
    "color": OPEN_CAFE_COLOUR,
}]

# Getting chaingang leaders
TARGET_URL = "https://www.strava.com/segments/31554922?filter=overall"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3"
}


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def get_chaingang_top10():
    # Overall leader board
    response = requests2.get(TARGET_URL, headers=headers)
    webpage = response.text
    soup = BeautifulSoup(webpage, "lxml")
    table = soup.find(id='segment-leaderboard')
    rows = []
    for i, row in enumerate(table.find_all('tr')):
        if i != 0:
            rows.append([el.text.strip() for el in row.find_all('td')])
    return rows


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/chaingang', methods=['GET'])
@update_last_seen
def chaingang():
    # -------------------------------------------------------------------------------------------- #
    # Show chaingang route
    # -------------------------------------------------------------------------------------------- #

    # ----------------------------------------------------------- #
    # Double check GPX file actually exists
    # ----------------------------------------------------------- #

    # This is  the absolute path to the file
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, CHAINGANG_GPX_FILENAME)

    # Check it exists before we try and parse it etc
    if not os.path.exists(filename):
        # Should never happen, but may as well handle it cleanly
        flash("Sorry, we seem to have lost that GPX file!")
        flash("Somebody should probably fire the web developer...")
        EventRepository().log_event("One GPX Fail", f"Can't find '{filename}'!")
        app.logger.error(f"gpx_details(): Can't find '{filename}'!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Need path as weird Google proprietary JSON string thing
    # ----------------------------------------------------------- #
    polyline = polyline_json(filename)

    # ----------------------------------------------------------- #
    # Need cafe markers as weird Google proprietary JSON string
    # ----------------------------------------------------------- #
    cafe_markers = CHAINGANG_MEET_NEW

    # ----------------------------------------------------------- #
    # Get elevation data
    # ----------------------------------------------------------- #
    elevation_data = get_elevation_data(filename)

    # ----------------------------------------------------------- #
    # Leader boards from Strava
    # ----------------------------------------------------------- #
    leader_table = get_chaingang_top10()

    # Increment map counts
    count_map_loads(1)

    # Render home page
    return render_template("main_chaingang.html", year=current_year, leader_table=leader_table,
                           cafe_markers=cafe_markers, elevation_data=elevation_data, live_site=live_site(),
                           polyline=polyline['polyline'], midlat=polyline['midlat'], midlon=polyline['midlon'],
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS)

