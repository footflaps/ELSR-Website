from flask import render_template


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our Decorators
# -------------------------------------------------------------------------------------------------------------- #

from core.decorators.user_decorators import update_last_seen


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.cafe_repository import OPEN_CAFE_COLOUR
from core.subs_google_maps import google_maps_api_key, MAP_BOUNDS, count_map_loads


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# TWR
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/twr', methods=['GET'])
@update_last_seen
def twr():
    # -------------------------------------------------------------------------------------------- #
    # Show The Bench
    # -------------------------------------------------------------------------------------------- #
    cafe_marker = [{
        "position": {"lat": 52.197020, "lng": 0.111206},
        "title": "The Bench",
        "color": OPEN_CAFE_COLOUR,
    }]

    # Increment map counts
    count_map_loads(1)

    # Render page
    return render_template("main_twr.html", year=current_year, cafes=cafe_marker, live_site=live_site(),
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS)


# -------------------------------------------------------------------------------------------------------------- #
# Tim's Turbo Sessions
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/turbo_training', methods=['GET'])
@update_last_seen
def turbo_training():

    # Render page
    return render_template("main_turbo_training.html", year=current_year, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Mallorca 2024
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/mallorca_2024', methods=['GET'])
@update_last_seen
def mallorca_2024():

    # Render page
    return render_template("main_mallorca_2024.html", year=current_year, live_site=live_site())


