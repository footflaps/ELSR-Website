from flask import render_template, request, flash, abort, send_from_directory, url_for, redirect
from flask_login import current_user
import gpxpy
import gpxpy.gpx
import os
import mpu


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, GPX_UPLOAD_FOLDER_ABS, is_mobile


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, update_last_seen
from core.subs_google_maps import polyline_json, google_maps_api_key, ELSR_HOME, MAP_BOUNDS, count_map_loads, \
                                  create_polyline_set, MAX_NUM_GPX_PER_GRAPH
from core.dB_gpx import Gpx
from subs_gpx import ELSR_LAT, ELSR_LON


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

REBELLION_WAY_INDEX = 115
PEDARS_WAY_INDEX = 116
WOLF_WAY_INDEX = 111
WOLF_CUB_INDEX = 113
WOLF_WINTER_INDEX = 112
WOLF_EAST_INDEX = 114

LOCAL_MAX_KM = 10


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
    # Render page
    # ----------------------------------------------------------- #
    return render_template("gravel_main.html", year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# All Gravel GPXes
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gravel/all', methods=['GET'])
@update_last_seen
def gravel_all():
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
    return render_template("gravel_all.html", year=current_year, gpxes=gpxes, mobile=is_mobile(),
                           missing_files=missing_files, GOOGLE_MAPS_API_KEY=google_maps_api_key(),
                           MAP_BOUNDS=MAP_BOUNDS, warning=warning,
                           polylines=polylines['polylines'], midlat=polylines['midlat'], midlon=polylines['midlon'])


# -------------------------------------------------------------------------------------------------------------- #
# Long Distance Trails
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gravel/ldt', methods=['GET'])
@update_last_seen
def gravel_ldt():
    # ----------------------------------------------------------- #
    # Grab the specific routes
    # ----------------------------------------------------------- #
    gpxes = [Gpx().one_gpx(REBELLION_WAY_INDEX),
             Gpx().one_gpx(PEDARS_WAY_INDEX),
             Gpx().one_gpx(WOLF_WAY_INDEX),
             Gpx().one_gpx(WOLF_CUB_INDEX),
             Gpx().one_gpx(WOLF_WINTER_INDEX),
             Gpx().one_gpx(WOLF_EAST_INDEX)]

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
    return render_template("gravel_ldt.html", year=current_year, gpxes=gpxes, mobile=is_mobile(),
                           missing_files=missing_files, GOOGLE_MAPS_API_KEY=google_maps_api_key(),
                           MAP_BOUNDS=MAP_BOUNDS, warning=warning,
                           polylines=polylines['polylines'], midlat=polylines['midlat'], midlon=polylines['midlon'])


# -------------------------------------------------------------------------------------------------------------- #
# LocalTrails
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gravel/local', methods=['GET'])
@update_last_seen
def gravel_local():
    # ----------------------------------------------------------- #
    # Start with all gravel
    # ----------------------------------------------------------- #
    all_gpxes = Gpx().all_gravel()

    # ----------------------------------------------------------- #
    # Filter by start location
    # ----------------------------------------------------------- #
    local_gpxes = []

    for gpx in all_gpxes:
        # Use absolute path for filename
        filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

        # Check GPX file actually exists
        if os.path.exists(filename):

            # Open the file
            with open(filename, 'r') as file_ref:
                gpx_file = gpxpy.parse(file_ref)
                start_lat = gpx_file.tracks[0].segments[0].points[0].latitude
                start_lon = gpx_file.tracks[0].segments[0].points[0].longitude
                range_km = mpu.haversine_distance((start_lat, start_lon), (ELSR_LAT, ELSR_LON))
                if range_km < LOCAL_MAX_KM:
                    local_gpxes.append(gpx)

    # ----------------------------------------------------------- #
    # Double check we have all the files present
    # ----------------------------------------------------------- #
    missing_files = []
    for gpx in local_gpxes:
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
    polylines = create_polyline_set(local_gpxes)

    # Warn if we skipped any
    if len(local_gpxes) > MAX_NUM_GPX_PER_GRAPH:
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
    return render_template("gravel_local.html", year=current_year, gpxes=local_gpxes, mobile=is_mobile(),
                           missing_files=missing_files, GOOGLE_MAPS_API_KEY=google_maps_api_key(),
                           MAP_BOUNDS=MAP_BOUNDS, warning=warning,
                           polylines=polylines['polylines'], midlat=polylines['midlat'], midlon=polylines['midlon'])

