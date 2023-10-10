from flask import render_template, request, flash, abort, send_from_directory, url_for, redirect
from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFError
from wtforms import StringField, EmailField, SubmitField
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from threading import Thread
import os
import requests
from bs4 import BeautifulSoup


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, GPX_UPLOAD_FOLDER_ABS, is_mobile


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe, OPEN_CAFE_COLOUR, BEAN_THEORY_INDEX
from core.db_users import User, update_last_seen
from core.subs_graphjs import get_elevation_data
from core.subs_google_maps import polyline_json, google_maps_api_key, ELSR_HOME, MAP_BOUNDS, count_map_loads, \
                                  create_polyline_set, MAX_NUM_GPX_PER_GRAPH
from core.dB_events import Event
from core.subs_email_sms import contact_form_email
from core.dB_gpx import Gpx


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Gravel Main
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gravel', methods=['GET'])
@update_last_seen
def gravel():
    # ----------------------------------------------------------- #
    # Grab all our routes
    # ----------------------------------------------------------- #
    gpxes = Gpx().all_gravel()

    # ----------------------------------------------------------- #
    # Double check we have all the files present
    # ----------------------------------------------------------- #
    missing_files = []
    for gpx in gpxes:
        # Absolute path name
        filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

        # Check the file is actually there, before we try and parse it etc
        if not os.path.exists(filename):
            missing_files.append(gpx.id)

    # Need different path for Admin
    if not current_user.is_authenticated:
        admin = False
    elif current_user.admin():
        admin = True
    else:
        admin = False

    if admin:
        for missing in missing_files:
            flash(f"We are missing the GPX file for route {missing}!")

    # ----------------------------------------------------------- #
    # Map for the possible routes
    # ----------------------------------------------------------- #
    polylines = create_polyline_set(gpxes)

    # Warn if we skipped any
    if len(gpxes) > MAX_NUM_GPX_PER_GRAPH:
        warning = f"NB: Only showing first {MAX_NUM_GPX_PER_GRAPH} routes on map."
    else:
        warning = None

    # ----------------------------------------------------------- #
    # Add to map counts
    # ----------------------------------------------------------- #
    if polylines['polylines']:
        count_map_loads(1)

    # ----------------------------------------------------------- #
    # Render page
    # ----------------------------------------------------------- #
    return render_template("gravel_main.html", year=current_year, gpxes=gpxes, mobile=is_mobile(),
                           missing_files=missing_files, GOOGLE_MAPS_API_KEY=google_maps_api_key(),
                           MAP_BOUNDS=MAP_BOUNDS, warning=warning,
                           polylines=polylines['polylines'], midlat=polylines['midlat'], midlon=polylines['midlon'])


# -------------------------------------------------------------------------------------------------------------- #
# Gravel Long Distance Trails
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gravel/ldt', methods=['GET'])
@update_last_seen
def gravel_ldt():
    # ----------------------------------------------------------- #
    # Grab all our routes
    # ----------------------------------------------------------- #
    gpxes = []



    Gpx().all_gravel()

    # ----------------------------------------------------------- #
    # Double check we have all the files present
    # ----------------------------------------------------------- #
    missing_files = []
    for gpx in gpxes:
        # Absolute path name
        filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

        # Check the file is actually there, before we try and parse it etc
        if not os.path.exists(filename):
            missing_files.append(gpx.id)

    # Need different path for Admin
    if not current_user.is_authenticated:
        admin = False
    elif current_user.admin():
        admin = True
    else:
        admin = False

    if admin:
        for missing in missing_files:
            flash(f"We are missing the GPX file for route {missing}!")

    # ----------------------------------------------------------- #
    # Map for the possible routes
    # ----------------------------------------------------------- #
    polylines = create_polyline_set(gpxes)

    # Warn if we skipped any
    if len(gpxes) > MAX_NUM_GPX_PER_GRAPH:
        warning = f"NB: Only showing first {MAX_NUM_GPX_PER_GRAPH} routes on map."
    else:
        warning = None

    # ----------------------------------------------------------- #
    # Add to map counts
    # ----------------------------------------------------------- #
    if polylines['polylines']:
        count_map_loads(1)

    # ----------------------------------------------------------- #
    # Render page
    # ----------------------------------------------------------- #
    return render_template("gravel_main.html", year=current_year, gpxes=gpxes, mobile=is_mobile(),
                           missing_files=missing_files, GOOGLE_MAPS_API_KEY=google_maps_api_key(),
                           MAP_BOUNDS=MAP_BOUNDS, warning=warning,
                           polylines=polylines['polylines'], midlat=polylines['midlat'], midlon=polylines['midlon'])