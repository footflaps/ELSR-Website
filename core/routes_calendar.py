from flask import render_template, url_for, request, flash, redirect, abort
from flask_login import login_required, current_user
from werkzeug import exceptions
from bbc_feeds import weather
from datetime import datetime, timedelta
import calendar as cal
import json
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, delete_file_if_exists

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe, OPEN_CAFE_COLOUR, CLOSED_CAFE_COLOUR
from core.subs_google_maps import create_polyline_set, MAX_NUM_GPX_PER_GRAPH, ELSR_HOME, MAP_BOUNDS, GOOGLE_MAPS_API_KEY
from core.dB_gpx import Gpx
from core.subs_gpx import allowed_file, GPX_UPLOAD_FOLDER_ABS
from core.dB_events import Event
from core.db_users import User, update_last_seen, logout_barred_user
from core.subs_graphjs import get_elevation_data_set, get_destination_cafe_height
from core.db_calendar import Calendar, CreateRideForm, AdminCreateRideForm, NEW_CAFE, UPLOAD_ROUTE, DEFAULT_START
from core.subs_gpx_edit import strip_excess_info_from_gpx


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

@app.route('/calendar', methods=['GET'])
@logout_barred_user
@update_last_seen
def calendar():
    # ----------------------------------------------------------- #
    # Need to build a list of events
    # ----------------------------------------------------------- #

    events = []

    # Loop over time
    this_year = datetime.today().year
    this_month = datetime.today().month

    # Just cover next 6 months
    for month in range(this_month, this_month + 2):
        if month == 13:
            this_year += 1
        for day in range(1, cal.monthrange(this_year, month % 12)[1] + 1):
            datestr = f"{format(day, '02d')}{format(month % 12, '02d')}{this_year}"
            if Calendar().all_calendar_date(datestr):
                print(f"Have event on {datestr}")
                events.append({
                    "date": f"{this_year}-{format(month % 12, '02d')}-{format(day, '02d')}",
                    "markup": f"<a href='{url_for('weekend', date=f'{datestr}')}'><i class='fas fa-solid fa-person-biking fa-2xl'></i>[day]</a>",
                })

    # Add a social
    events.append({
             "date": "2023-08-02",
             "markup": '<i class="fas fa-solid fa-champagne-glasses fa-2xl"></i>[day]'
    })

    return render_template("calendar.html", year=current_year, events=events)

