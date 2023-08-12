import random
from flask import render_template, redirect, url_for, flash, request, abort, send_from_directory
from flask_login import login_required, current_user
from flask_googlemaps import Map
from werkzeug import exceptions
import gpxpy
import gpxpy.gpx
import mpu
import os
from time import sleep
from threading import Thread
from datetime import datetime, timedelta


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS, dynamic_map_size, dynamic_graph_size, \
                 current_year, delete_file_if_exists, is_mobile


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_gpx import Gpx, UploadGPXForm, GPX_ALLOWED_EXTENSIONS
from core.db_users import User, update_last_seen, logout_barred_user
from core.dB_cafes import Cafe, OPEN_CAFE_ICON, CLOSED_CAFE_ICON
from core.dB_events import Event


# -------------------------------------------------------------------------------------------------------------- #
# Constants used to verify sensible cafe coordinates
# -------------------------------------------------------------------------------------------------------------- #

# We only allow cafes within a sensible range to Cambridge (Espresso Library Cafe)
ELSR_LAT = 52.203316
ELSR_LON = 0.131689
ELSR_MAX_KM = 100

# We only associate a cafe with a route if it passes within a sensible range of the cafe
MIN_DIST_TO_CAFE_KM = 1

# GPX trails can have many points very close together, these look terrible in GM with an icon for each point
# so we filter the points with a minimum inter point distance, before passing to GM.
MIN_DISPLAY_STEP_KM = 0.5

# Remove any points closer together than this
GPX_MAX_RESOLUTION_KM = 0.05

# How far we display along the route for trimming start and end
TRIM_DISTANCE_KM = 2.0

# Map icon
# The icon gets located by its centre, but really needs to have it's lower point sat on the line,
# so frig this by moving it up a bit.
FUDGE_FACTOR_m = 10


# -------------------------------------------------------------------------------------------------------------- #
# Ensure only GPX files get uploaded
# -------------------------------------------------------------------------------------------------------------- #

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in GPX_ALLOWED_EXTENSIONS


# -------------------------------------------------------------------------------------------------------------- #
# Update all GPXes with a new cafe
# -------------------------------------------------------------------------------------------------------------- #

def check_new_cafe_with_all_gpxes(cafe):
    app.logger.debug(f"check_new_cafe_with_all_gpxes(): Called with '{cafe.name}'.")

    # Get all the routes
    gpxes = Gpx().all_gpxes()

    # Loop over each GPX file
    for gpx in gpxes:

        # Use absolute path for filename
        filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))

        # Open the file
        with open(filename, 'r') as file_ref:
            gpx_file = gpxpy.parse(file_ref)

            # Max distance
            min_km = 100
            dist_km = 0
            min_km_dist = 100

            for track in gpx_file.tracks:
                for segment in track.segments:

                    last_lat = segment.points[0].latitude
                    last_lon = segment.points[0].longitude

                    for point in segment.points:

                        # How far along the route we are
                        dist_km += mpu.haversine_distance((last_lat, last_lon), (point.latitude, point.longitude))

                        # How far is the cafe from the GPX file
                        range_km = mpu.haversine_distance((cafe.lat, cafe.lon), (point.latitude, point.longitude))

                        if range_km < min_km:
                            min_km = range_km
                            min_km_dist = dist_km

                        last_lat = point.latitude
                        last_lon = point.longitude

        # Close enough?
        if min_km <= MIN_DIST_TO_CAFE_KM:
            app.logger.debug(f"-- Closest to cafe {cafe.name} was {round(min_km, 1)} km"
                             f" at {round(min_km_dist, 1)} km along the route. Total length was {round(dist_km, 1)} km")
            Gpx().update_cafe_list(gpx.id, cafe.id, round(min_km, 1), round(min_km_dist, 1))
        else:
            Gpx().remove_cafe_list(gpx.id, cafe.id)


# -------------------------------------------------------------------------------------------------------------- #
# Update a GPX from existing cafe dB
# -------------------------------------------------------------------------------------------------------------- #

def check_new_gpx_with_all_cafes(gpx_id):
    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    # Make sure gpx_id is valid
    if not gpx:
        app.logger.debug(f"check_new_gpx_with_all_cafes(): Failed to locate GPX: gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Fail", f"Failed to locate GPX: gpx_id = '{gpx_id}'.")
        return False

    app.logger.debug(f"check_new_gpx_with_all_cafes(): Updating GPX '{gpx.name}' for closeness to all cafes.")
    Event().log_event("Update GPX", f"Updating GPX '{gpx.name}' for closeness to all cafes.'")

    # ----------------------------------------------------------- #
    # Get all the cafes
    # ----------------------------------------------------------- #
    cafes = Cafe().all_cafes()

    # Need a list of closeness
    min_distance_km = [100] * len(cafes)
    min_distance_path_km = [0] * len(cafes)

    # ----------------------------------------------------------- #
    # Loop over the GPX file
    # ----------------------------------------------------------- #

    # Use absolute path for filename
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))

    with open(filename, 'r') as file_ref:

        gpx_file = gpxpy.parse(file_ref)

        for track in gpx_file.tracks:
            for segment in track.segments:

                last_lat = segment.points[0].latitude
                last_lon = segment.points[0].longitude
                dist_along_route_km = 0

                for point in segment.points:

                    # How far along the route we are
                    dist_along_route_km += mpu.haversine_distance((last_lat, last_lon),
                                                                  (point.latitude, point.longitude))

                    for cafe in cafes:

                        # How far is the cafe from the GPX file
                        dist_to_cafe_km = mpu.haversine_distance((cafe.lat, cafe.lon),
                                                                 (point.latitude, point.longitude))

                        if dist_to_cafe_km < min_distance_km[cafe.id - 1]:
                            min_distance_km[cafe.id - 1] = dist_to_cafe_km
                            min_distance_path_km[cafe.id - 1] = dist_along_route_km

                    last_lat = point.latitude
                    last_lon = point.longitude

        # ----------------------------------------------------------- #
        # Summarise what we found
        # ----------------------------------------------------------- #
        for cafe in cafes:
            if min_distance_km[cafe.id - 1] <= MIN_DIST_TO_CAFE_KM:
                app.logger.debug(f"-- Route passes within {round(min_distance_km[cafe.id - 1],1)} km of {cafe.name} "
                                 f"after {round(min_distance_path_km[cafe.id - 1],1)} km.")
                # Push update to GPX file
                Gpx().update_cafe_list(gpx.id, cafe.id, min_distance_km[cafe.id - 1],
                                       min_distance_path_km[cafe.id - 1])


# gpx = Gpx().one_gpx(11)
# check_new_gpx_with_all_cafes(gpx)

# 5 is Mill End Plants
# for cafe in Cafe().all_cafes():
#     check_new_cafe_with_all_gpxes(cafe)


# -------------------------------------------------------------------------------------------------------------- #
# Update existing file
# -------------------------------------------------------------------------------------------------------------- #

def update_existing_gpx(gpx_file, gpx_filename):

    # This is the full path to the existing GPX file we are going to over write
    old_filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx_filename)))

    # This is a temp file we will use to write out the new GPX file to first
    tmp_filename = f"{old_filename}.tmp"

    # ----------------------------------------------------------- #
    # Step 1: Delete tmp file if it exists
    # ----------------------------------------------------------- #
    # NB It shouldn't exist, but if something went wrong with a deleted GPX, it could end up left orphaned
    if os.path.exists(tmp_filename):
        try:
            os.remove(tmp_filename)
            # We need this as remove seems to keep the file locked for a short period
            sleep(0.5)
        except Exception as e:
            app.logger.debug(f"update_existing_gpx(): Failed to delete existing file '{tmp_filename}', "
                             f"error code was '{e.args}'.")
            Event().log_event("GPX Fail",
                              f"Failed to delete existing file '{tmp_filename}', error code was '{e.args}'.")
            return False

    # ----------------------------------------------------------- #
    # Step 2: Write out our shortened file to new_filename
    # ----------------------------------------------------------- #
    try:
        with open(tmp_filename, 'w') as file_ref2:
            file_ref2.write(gpx_file.to_xml())
    except Exception as e:
        Event().log_event("GPX Fail", f"Failed to write file '{tmp_filename}', error code was '{e.args}'.")
        app.logger.debug(f"update_existing_file: Failed to write file '{tmp_filename}', error code was '{e.args}'.")
        return False

    # ----------------------------------------------------------- #
    # Step 3: Delete the existing (unshortened) GPX file
    # ----------------------------------------------------------- #
    try:
        os.remove(old_filename)
        # We need this as remove seems to keep the file locked for a short period
        sleep(0.5)
    except Exception as e:
        Event().log_event("GPX Fail", f"Failed to delete existing file '{old_filename}', error code was '{e.args}'.")
        app.logger.debug(f"update_existing_file: Failed to delete existing file '{old_filename}', "
                         f"error code was '{e.args}'.")
        return False

    # ----------------------------------------------------------- #
    # Step 4: Rename our temp (shortened) file
    # ----------------------------------------------------------- #
    try:
        os.rename(tmp_filename, old_filename)
    except Exception as e:
        Event().log_event("GPX Fail", f"Failed to rename existing file '{tmp_filename}', error code was '{e.args}'.")
        app.logger.debug(f"update_existing_file: Failed to rename existing file '{tmp_filename}', "
                         f"error code was '{e.args}'.")
        return False

    # All worked if we get here!
    return True


# -------------------------------------------------------------------------------------------------------------- #
# Cut the end of the start of the GPX
# -------------------------------------------------------------------------------------------------------------- #

def cut_start_gpx(gpx_filename, start_count):
    Event().log_event("GPX cut Start", f"Called with gpx_filename='{gpx_filename}', start_count='{start_count}'.")
    app.logger.debug(f"cut_start_gpx: Called with gpx_filename='{gpx_filename}', start_count='{start_count}'.")

    # ----------------------------------------------------------- #
    # Open the file and trim it
    # ----------------------------------------------------------- #

    # Use absolute path for filename
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx_filename)))

    with open(filename, 'r') as file_ref:
        gpx_file = gpxpy.parse(file_ref)

        # Read in all points after start_count
        for track in gpx_file.tracks:

            count_before = len(track.segments[0].points)

            for segment in track.segments:
                # ----------------------------------------------------------- #
                # Strip start_count points from the beginning
                # ----------------------------------------------------------- #
                for _ in range(max(start_count - 1, 0)):
                    segment.points.pop(0)

            count_after = len(track.segments[0].points)

    # ----------------------------------------------------------- #
    # Overwrite the existing file with the new file
    # ----------------------------------------------------------- #
    update_existing_gpx(gpx_file, gpx_filename)
    Event().log_event("GPX cut Start", f"Length was {count_before}, now {count_after}. gpx_filename = '{gpx_filename}'")
    app.logger.debug(f"cut_start_gpx: Length was {count_before}, now {count_after}. gpx_filename = '{gpx_filename}'")


# -------------------------------------------------------------------------------------------------------------- #
# Crop the end of the GPX file
# -------------------------------------------------------------------------------------------------------------- #
def cut_end_gpx(gpx_filename, end_count):
    Event().log_event("GPX cut End", f"Called with gpx_filename='{gpx_filename}', end_count='{end_count}'.")
    app.logger.debug(f"cut_end_gpx: Called with gpx_filename='{gpx_filename}', end_count='{end_count}'.")

    # ----------------------------------------------------------- #
    # Open the file and trim it
    # ----------------------------------------------------------- #
    # Use absolute path for filename
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx_filename)))

    with open(filename, 'r') as file_ref:
        gpx_file = gpxpy.parse(file_ref)

        # Read in all points after start_count
        for track in gpx_file.tracks:

            count_before = len(track.segments[0].points)

            for segment in track.segments:

                # ----------------------------------------------------------- #
                # Strip start_count points from the beginning
                # ----------------------------------------------------------- #
                num_points = len(segment.points)
                num_to_crop = num_points - end_count

                for _ in range(num_to_crop):
                    segment.points.pop(-1)

                count_after = len(track.segments[0].points)

    # ----------------------------------------------------------- #
    # Overwrite the existing file with the new file in 4 steps
    # ----------------------------------------------------------- #
    update_existing_gpx(gpx_file, gpx_filename)
    Event().log_event("GPX cut End", f"Length was {count_before}, now {count_after}. gpx_filename = '{gpx_filename}'.")
    app.logger.debug(f"cut_end_gpx: Length was {count_before}, now {count_after}. gpx_filename = '{gpx_filename}'.")


# -------------------------------------------------------------------------------------------------------------- #
# New "clean" GPX file
# -------------------------------------------------------------------------------------------------------------- #

def new_gpx(route_name):
    gpx = gpxpy.gpx.GPX()

    # Create first track in our GPX:
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_track.name = route_name
    gpx.tracks.append(gpx_track)

    # Create first segment in our GPX track:
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    return gpx


# -------------------------------------------------------------------------------------------------------------- #
# Make sure the GPX file has an up to date name
# -------------------------------------------------------------------------------------------------------------- #

def check_route_name(gpx):

    # ----------------------------------------------------------- #
    # Use absolute path
    # ----------------------------------------------------------- #
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))

    # ----------------------------------------------------------- #
    # Params we will add
    # ----------------------------------------------------------- #

    # This is the name which will appear in the Garmin etc
    route_name = f"ELSR: {gpx.name}"
    route_link = f"https://www.elsr.co.uk/route/{gpx.id}"

    # ----------------------------------------------------------- #
    # Open the file
    # ----------------------------------------------------------- #
    with open(filename, 'r') as file_ref:
        gpx_file = gpxpy.parse(file_ref)
        gpx_track = gpx_file.tracks[0]

        # Looks like we need to add the time stamps back in otherwise Strava won't import it
        # But Strava is fussy about timestamps, so not too fast, not too slow and it appears
        # they need to have a random element.
        for track in gpx_file.tracks:
            for segment in track.segments:
                last_time = datetime.now()
                for point in segment.points:
                    point.time = last_time + timedelta(minutes=3, seconds=random.randint(0, 120))

    # Update our params
    gpx_file.author_name = "ELSR website"
    gpx_file.author_link = route_link
    gpx_file.name = route_name
    gpx_track.name = route_name
    gpx_track.link = route_link
    gpx_track.type = "cycling"

    # Refresh the file
    update_existing_gpx(gpx_file, filename)
    app.logger.debug(f"check_route_name(): Updated name for GPX '{filename}' to '{route_name}'.")


# -------------------------------------------------------------------------------------------------------------- #
# Clean up the GPX file
# -------------------------------------------------------------------------------------------------------------- #

def strip_excess_info_from_gpx(gpx_filename, gpx_id, route_name):
    # ----------------------------------------------------------- #
    # Header
    # ----------------------------------------------------------- #
    app.logger.debug(f"strip_excess_info_from_gpx(): Called with gpx_filename='{gpx_filename}', gpx_id='{gpx_id}'.")

    # ----------------------------------------------------------- #
    # Use absolute path
    # ----------------------------------------------------------- #
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx_filename)))

    # ----------------------------------------------------------- #
    # Generate stats for updating the dB route summary
    # ----------------------------------------------------------- #
    total_length_km = 0
    total_ascent_m = 0
    num_points_before = 0
    num_points_after = 0

    # ----------------------------------------------------------- #
    # Create a new GPX object
    # ----------------------------------------------------------- #
    # For some reason we can't delete the extension data from a GPX file (HR, cadence, power). So, the bodge is
    # just to create a new file and migrate across only the data we want (lat, lon, height).
    new_gpx_file = new_gpx(route_name)

    # ----------------------------------------------------------- #
    # Open the file
    # ----------------------------------------------------------- #
    with open(filename, 'r') as file_ref:
        gpx_file = gpxpy.parse(file_ref)

        # Read in all points after start_count
        for track in gpx_file.tracks:

            for segment in track.segments:

                # Set these to zero, so we always include the first point, otherwise it skips the first
                # few points till we have moved along the route past GPX_MAX_RESOLUTION_KM
                last_lat = segment.points[0].latitude
                last_lon = segment.points[0].longitude
                last_elevation = segment.points[0].elevation

                # From our new GPX file
                saved_lat = 0
                saved_lon = 0

                for point in segment.points:

                    # ----------------------------------------------------------- #
                    # Route stats come from original file (higher resolution)
                    # ----------------------------------------------------------- #
                    inter_dist_km = mpu.haversine_distance((last_lat, last_lon), (point.latitude, point.longitude))
                    total_length_km += inter_dist_km
                    num_points_before += 1

                    # Total ascent
                    if point.elevation > last_elevation:
                        total_ascent_m += point.elevation - last_elevation

                    # Update last point
                    last_lat = point.latitude
                    last_lon = point.longitude
                    last_elevation = point.elevation

                    # ----------------------------------------------------------- #
                    # How far is this point from the previous saved one?
                    # ----------------------------------------------------------- #
                    inter_dist_km = mpu.haversine_distance((saved_lat, saved_lon), (point.latitude, point.longitude))

                    if inter_dist_km >= GPX_MAX_RESOLUTION_KM:

                        # Create a new point, using just the data we want
                        new_point = gpxpy.gpx.GPXTrackPoint(point.latitude,
                                                            point.longitude,
                                                            point.elevation)

                        # Add to out new GPX file
                        new_gpx_file.tracks[0].segments[0].points.append(new_point)
                        num_points_after += 1

                        # Update last point
                        saved_lat = point.latitude
                        saved_lon = point.longitude

    # ----------------------------------------------------------- #
    # Update stats in the dB
    # ----------------------------------------------------------- #
    Gpx().update_stats(gpx_id, total_length_km, total_ascent_m)

    # ----------------------------------------------------------- #
    # Overwrite the existing file
    # ----------------------------------------------------------- #
    update_existing_gpx(new_gpx_file, gpx_filename)
    Event().log_event("Clean GPX", f"Culled from {num_points_before} to {num_points_after} points.")
    app.logger.debug(f"strip_excess_info_from_gpx(): Culled from {num_points_before} to {num_points_after} points.")


# -------------------------------------------------------------------------------------------------------------- #
# Markers for the complete GPX file (we subsample the file for Google Maps)
# -------------------------------------------------------------------------------------------------------------- #

def markers_for_gpx(filename):
    # Use absolute path for filename
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(filename)))

    # This is the list we will return
    markers = []
    with open(filename, 'r') as gpx_file:

        gpx_track = gpxpy.parse(gpx_file)

        for track in gpx_track.tracks:
            for segment in track.segments:

                # Need these for working out inter sample spacing
                last_lat = 0
                last_lon = 0
                count = 0

                for point in segment.points:

                    # We sub-sample the raw GPX file as if you plot all the points, the map looks a complete mess.
                    if mpu.haversine_distance((last_lat, last_lon),
                                              (point.latitude, point.longitude)) > MIN_DISPLAY_STEP_KM or \
                            point == segment.points[-1]:
                        count += 1

                        markers.append({
                            'icon': 'http://maps.google.com/mapfiles/kml/pal4/icon49.png',
                            'lat': point.latitude,
                            'lng': point.longitude,
                            'infobox': f'Point {count}'
                        })

                        last_lat = point.latitude
                        last_lon = point.longitude
    return markers


# -------------------------------------------------------------------------------------------------------------- #
# Markers for a set of cafes
# -------------------------------------------------------------------------------------------------------------- #

def markers_for_cafes(cafes):
    markers = []
    for cafe_summary in cafes:

        # Need to look up current cafe open / closed status
        if Cafe().one_cafe(cafe_summary["id"]).active:
            icon = OPEN_CAFE_ICON
        else:
            icon = CLOSED_CAFE_ICON

        markers.append({
            'icon': icon,
            'lat': cafe_summary['lat'],
            'lng': cafe_summary['lon'],
            'infobox': f'<a href="{url_for("cafe_details", cafe_id=cafe_summary["id"])}">{cafe_summary["name"]}</a>'
        })
    return markers


# -------------------------------------------------------------------------------------------------------------- #
# Generate the pair of maps for editing the start and end of a ride
# -------------------------------------------------------------------------------------------------------------- #

def start_and_end_maps(filename, gpx_id):
    # Use absolute path for filename
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(filename)))

    # Creating two separate maps:
    start_markers = []
    end_markers = []

    # open our file
    with open(filename, 'r') as gpx_file:
        gpx_track = gpxpy.parse(gpx_file)

        # ----------------------------------------------------------- #
        #   Markers for 1st 2km
        # ----------------------------------------------------------- #
        for track in gpx_track.tracks:
            for segment in track.segments:

                # Need these for working out inter sample spacing
                last_lat = segment.points[0].latitude
                last_lon = segment.points[0].longitude
                total_km = 0
                index = 0

                for point in segment.points:

                    # Work out how far we have travelled so far...
                    total_km += mpu.haversine_distance((last_lat, last_lon), (point.latitude, point.longitude))

                    index += 1

                    # We only want the first km or so
                    if total_km < TRIM_DISTANCE_KM:
                        start_markers.append({
                            'icon': 'http://maps.google.com/mapfiles/kml/pal4/icon49.png',
                            'lat': point.latitude,
                            'lng': point.longitude,
                            'infobox': f'<a href="{url_for("gpx_cut_start", gpx_id=gpx_id, index=index)}">Start Here! (Point {index})</a>'
                        })
                    else:
                        break

                    last_lat = point.latitude
                    last_lon = point.longitude

        # ----------------------------------------------------------- #
        #   Markers for last 2km
        # ----------------------------------------------------------- #
        for track in gpx_track.tracks:
            for segment in track.segments:

                # Need these for working out inter sample spacing
                last_lat = segment.points[-1].latitude
                last_lon = segment.points[-1].longitude
                total_km = 0
                index = len(segment.points)

                for point in segment.points[::-1]:

                    # Work out how far we have travelled so far...
                    total_km += mpu.haversine_distance((last_lat, last_lon), (point.latitude, point.longitude))

                    # We only want the last km or so
                    if total_km < TRIM_DISTANCE_KM:
                        end_markers.append({
                            'icon': 'http://maps.google.com/mapfiles/kml/pal4/icon49.png',
                            'lat': point.latitude,
                            'lng': point.longitude,
                            'infobox': f'<a href="{url_for("gpx_cut_end", gpx_id=gpx_id, index=index)}">Finish Here! (Point {index})</a>'
                        })
                    else:
                        break

                    last_lat = point.latitude
                    last_lon = point.longitude
                    index -= 1

    # Create the Google Map config
    startmap = Map(
        identifier="startmap",
        lat=52.211001,
        lng=0.117207,
        fit_markers_to_bounds=True,
        style=dynamic_map_size(),
        markers=start_markers
    )

    # Create the Google Map config
    endmap = Map(
        identifier="endmap",
        lat=52.211001,
        lng=0.117207,
        fit_markers_to_bounds=True,
        style=dynamic_map_size(),
        markers=end_markers
    )

    return [startmap, endmap]


# -------------------------------------------------------------------------------------------------------------- #
# Generate a line graph of the route's elevation
# -------------------------------------------------------------------------------------------------------------- #

def get_elevation_data(filename):

    # This is what we will populate from the GPX file
    points = []

    # open our file
    with open(filename, 'r') as gpx_file:
        gpx_track = gpxpy.parse(gpx_file)

        # ----------------------------------------------------------- #
        #   Generate our elevation graph data set
        # ----------------------------------------------------------- #
        for track in gpx_track.tracks:
            for segment in track.segments:

                # Need these for working out inter sample spacing
                last_lat = segment.points[0].latitude
                last_lon = segment.points[0].longitude
                total_km = 0

                for point in segment.points:
                    # Work out how far we have travelled so far...
                    total_km += mpu.haversine_distance((last_lat, last_lon), (point.latitude, point.longitude))

                    points.append({
                        'x': round(total_km, 1),
                        'y': round(point.elevation, 1)
                    })

                    last_lat = point.latitude
                    last_lon = point.longitude

    return points


# -------------------------------------------------------------------------------------------------------------- #
# Generate icons for the cafes which match route elevation
# -------------------------------------------------------------------------------------------------------------- #

def get_cafe_heights(cafe_list, elevation_data):

    # This is what we will return
    cafe_elevation_data = []

    for cafe in cafe_list:
        # Extract the name and distance
        cafe_name = cafe['name']
        cafe_dist = float(cafe['range_km'])

        # Find closest point in terms of distance along the route and then
        # use the elevation of that point for the cafe icon.
        closet_km = 100
        elevation = 0

        # Now find elevation...
        for point in elevation_data:

            # Delta between distance along route of this point and our cafe's distance along the route
            delta_km = abs(float(point['x']) - cafe_dist)
            if delta_km < closet_km:
                # New closest point
                closet_km = delta_km
                elevation = point['y']

        # Have all we need for this cafe's entry
        cafe_elevation_data.append({
            'name': cafe_name,
            'coord':
                {
                    'x': cafe_dist,
                    'y': elevation + FUDGE_FACTOR_m
                }
        })

    return cafe_elevation_data


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# List of all known GPX files
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/routes', methods=['GET'])
@update_last_seen
def gpx_list():

    # Grab all our routes
    gpxes = Gpx().all_gpxes()

    # Render in gpx_list template
    return render_template("gpx_list.html", year=current_year,  gpxes=gpxes, mobile=is_mobile())


# -------------------------------------------------------------------------------------------------------------- #
# Display a single GPX file
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/route/<int:gpx_id>', methods=['GET'])
@update_last_seen
def gpx_details(gpx_id):

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"gpx_details(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("One GPX Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Route must be public
    # Tortuous logic as a non logged-in user doesn't have any of our custom attributes eg email etc
    if not gpx.public() and \
       not current_user.is_authenticated:
        app.logger.debug(f"gpx_details(): Refusing permission for non logged in user and hidden route '{gpx_id}'.")
        Event().log_event("One GPX Fail", f"Refusing permission for non logged in user and hidden route '{gpx_id}'.")
        return abort(403)

    elif not gpx.public() and \
         current_user.email != gpx.email and \
         not current_user.admin():
        app.logger.debug(f"gpx_details(): Refusing permission for user '{current_user.email}' to see "
                         f"hidden GPX route '{gpx.id}'!")
        Event().log_event("One GPX Fail", f"Refusing permission for user {current_user.email} to see "
                                          f"hidden GPX route, gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Get info for webpage
    # ----------------------------------------------------------- #
    author = User().find_user_from_email(gpx.email).name
    cafe_list = Cafe().cafe_list(gpx.cafes_passed)

    # ----------------------------------------------------------- #
    # Double check GPX file actually exists
    # ----------------------------------------------------------- #

    # This is the absolute path to the file
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))

    # Check the file is actually there, before we try and parse it etc
    if not os.path.exists(filename):
        # Should never happen, but may as well handle it cleanly
        app.logger.debug(f"gpx_details(): Can't find '{filename}'!")
        Event().log_event("One GPX Fail", f"Can't find '{filename}'!")
        flash("Sorry, we seem to have lost that GPX file!")
        flash("Someone should probably fire the web developer...")
        return abort(404)

    # ----------------------------------------------------------- #
    # Need a map of the route and nearby cafes
    # ----------------------------------------------------------- #
    markers = markers_for_gpx(gpx.filename)
    markers += markers_for_cafes(cafe_list)
    sndmap = Map(
        identifier="cafemap",
        lat=52.211001,
        lng=0.117207,
        fit_markers_to_bounds=True,
        style=dynamic_map_size(),
        markers=markers
    )

    # ----------------------------------------------------------- #
    # Get elevation data
    # ----------------------------------------------------------- #
    elevation_data = get_elevation_data(filename)
    cafe_elevation_data = get_cafe_heights(cafe_list, elevation_data)
    graph_width = dynamic_graph_size()

    # ----------------------------------------------------------- #
    # Flag if hidden
    # ----------------------------------------------------------- #
    if not gpx.public():
        flash("This route is not public yet!")

    # Render in main index template
    return render_template("gpx_details.html", gpx=gpx, year=current_year, sndmap=sndmap,
                           author=author, cafe_list=cafe_list, elevation_data=elevation_data,
                           cafe_elevation_data=cafe_elevation_data, graph_width=graph_width)


# -------------------------------------------------------------------------------------------------------------- #
# Make a route public
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/publish_route', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def publish_route():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"publish_route(): Missing gpx_id!")
        Event().log_event("Publish GPX Fail", f"Missing gpx_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"publish_route(): Failed to locate GPX with gpx_id = '{gpx_id}'!")
        Event().log_event("Publish GPX Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
            or not current_user.can_post_gpx():
        # Failed authentication
        app.logger.debug(f"publish_route(): Refusing permission for '{current_user.email}' to and route '{gpx.id}'!")
        Event().log_event("Publish GPX Fail", f"Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Publish route
    # ----------------------------------------------------------- #
    if Gpx().publish(gpx_id):
        app.logger.debug(f"publish_route(): Route published gpx.id = '{gpx.id}'.")
        Event().log_event("Publish GPX Success", f"Route published with gpx_id = '{gpx_id}'.")
        flash("Route has been published!")
    else:
        app.logger.debug(f"publish_route(): Failed to publish route gpx.id = '{gpx.id}'.")
        Event().log_event("Publish GPX Fail", f"Failed to publish, gpx_id = '{gpx_id}'.")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Clear existing nearby cafe list
    # ----------------------------------------------------------- #
    if not Gpx().clear_cafe_list(gpx_id):
        app.logger.debug(f"publish_route(): Failed clear cafe list gpx.id = '{gpx.id}'.")
        Event().log_event("Publish GPX Fail", f"Failed clear cafe list, gpx_id = '{gpx_id}'.")
        flash("Sorry, something went wrong!")
        return redirect(url_for('edit_route', gpx_id=gpx_id))

    # ----------------------------------------------------------- #
    # Add new existing nearby cafe list
    # ----------------------------------------------------------- #
    flash("Nearby cafe list is being updated.")
    Thread(target=check_new_gpx_with_all_cafes, args=(gpx_id,)).start()

    # Redirect back to the details page as the route is now public, ie any editing is over
    return redirect(url_for('gpx_details', gpx_id=gpx_id))


# -------------------------------------------------------------------------------------------------------------- #
# Make a route private
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/hide_route', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def hide_route():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"hide_route(): Missing gpx_id!")
        Event().log_event("Hide GPX Fail", f"Missing gpx_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"hide_route(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("Hide GPX Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
            or not current_user.can_post_gpx():
        # Failed authentication
        app.logger.debug(f"hide_route(): Refusing permission for {current_user.email} to "
                         f"and route gpx_id = '{gpx_id}'.")
        Event().log_event("Hide GPX Fail", f"Refusing permission for {current_user.email} to "
                                           f"and route gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Hide route
    # ----------------------------------------------------------- #
    if Gpx().hide(gpx_id):
        app.logger.debug(f"hide_route(): Route hidden gpx_id = '{gpx_id}'.")
        Event().log_event("Hide GPX Success", f"Route hidden gpx_id = '{gpx_id}'.")
        flash("Route has been hidden.")
    else:
        # Should never happen, but...
        app.logger.debug(f"hide_route(): Gpx().hide() failed for gpx_id = '{gpx_id}'.")
        Event().log_event("Hide GPX Fail", f"SGpx().hide() failed for gpx_id = '{gpx_id}'.")
        flash("Sorry, something went wrong!")

    # Redirect back to the edit page as that's probably what they want to do next
    return redirect(url_for('edit_route', gpx_id=gpx_id))


# -------------------------------------------------------------------------------------------------------------- #
# Add a GPX ride to the dB
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/new_route', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def new_route():
    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if not current_user.can_post_gpx():
        Event().log_event("New GPX Fail", f"Refusing permission for user {current_user.email} to upload GPX route!")
        app.logger.debug(f"new_route(): Refusing permission for user {current_user.email} to upload GPX route!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Need a form for uploading
    # ----------------------------------------------------------- #
    form = UploadGPXForm()

    # Are we posting the completed form?
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        #   POST - form submitted and validated
        # ----------------------------------------------------------- #

        # Try and get the filename.
        if 'filename' not in request.files:
            # Almost certain the form failed validation
            app.logger.debug(f"new_route(): Failed to find 'filename' in request.files!")
            Event().log_event(f"New GPX Fail", f"Failed to find 'filename' in request.files!")
            flash("Couldn't find the file.")
            return render_template("gpx_add.html", year=current_year, form=form)

        else:
            # Get the filename
            file = request.files['filename']
            app.logger.debug(f"new_route(): About to upload '{file}'.")

            # If the user does not select a file, the browser submits an
            # empty file without a filename.
            if file.filename == '':
                app.logger.debug(f"new_route(): No selected file!")
                Event().log_event(f"New GPX Fail", f"No selected file!")
                flash('No selected file')
                return redirect(request.url)

            if not file or \
               not allowed_file(file.filename):
                app.logger.debug(f"new_route(): Invalid file '{file.filename}'!")
                Event().log_event(f"New GPX Fail", f"Invalid file '{file.filename}'!")
                flash("That's not a GPX file!")
                return redirect(request.url)

            # Create a new GPX object
            # We do this first as we need the id in order to create
            # the filename for the GPX file when we upload it
            gpx = Gpx()
            gpx.name = form.name.data
            gpx.email = current_user.email
            gpx.cafes_passed = "[]"
            gpx.ascent_m = 0
            gpx.length_km = 0
            gpx.filename = "tmp"

            # Add to the dB
            new_id = gpx.add_gpx(gpx)
            if new_id:
                # Success, added GPX to dB
                # Have to re-get the GPX as it's changed since we created it
                gpx = Gpx().one_gpx(new_id)
                app.logger.debug(f"new_route(): GPX added to dB, id = '{gpx.id}'.")
                Event().log_event(f"New GPX Success", f" GPX added to dB, gpx.id = '{gpx.id}'.")
            else:
                # Failed to create new dB entry
                app.logger.debug(f"new_route(): Failed to add gpx to the dB!")
                Event().log_event(f"New GPX Fail", f"Failed to add gpx to the dB!")
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form)

            # This is where we will store it
            filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, f"gpx_{gpx.id}.gpx")
            app.logger.debug(f"new_route(): Filename will be = '{filename}'.")

            # Make sure this doesn't already exist
            if not delete_file_if_exists(filename):
                # Failed to delete existing file (func will generate error trace)
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form)

            # Upload the GPX file
            try:
                file.save(filename)
            except Exception as e:
                app.logger.debug(f"new_route(): Failed to upload/save '{filename}', error code was {e.args}.")
                Event().log_event(f"New GPX Fail", f"Failed to upload/save '{filename}', error code was {e.args}.")
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form)

            # Update gpx object with filename
            if not Gpx().update_filename(gpx.id, filename):
                app.logger.debug(f"new_route(): Failed to update filename in the dB for gpx_id='{gpx.id}'.")
                Event().log_event(f"New GPX Fail", f"Failed to update filename in the dB for gpx_id='{gpx.id}'.")
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form)

            # Strip all excess data from the file
            flash("Any HR or Power data has been removed.")
            strip_excess_info_from_gpx(filename, gpx.id, f"ELSR: {gpx.name}")

            # Forward to edit route as that's the next step
            app.logger.debug(f"new_route(): New GPX added, gpx_id = '{gpx.id}', ({gpx.name}).")
            Event().log_event(f"New GPX Success", f"New GPX added, gpx_id = '{gpx.id}', ({gpx.name}).")
            return redirect(url_for('edit_route', gpx_id=gpx.id))

    elif request.method == 'POST':

        # ----------------------------------------------------------- #
        #   POST - form validation failed
        # ----------------------------------------------------------- #
        flash("Form not filled in properly, see below!")

        return render_template("gpx_add.html", year=current_year, form=form)

    # ----------------------------------------------------------- #
    #   GET - render form etc
    # ----------------------------------------------------------- #

    return render_template("gpx_add.html", year=current_year, form=form)


# -------------------------------------------------------------------------------------------------------------- #
# Allow the user to edit a GPX file
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/edit_route', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def edit_route():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"edit_route(): Missing gpx_id!")
        Event().log_event("Edit GPX Fail", f"Missing gpx_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"edit_route(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("Edit GPX Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
       or not current_user.can_post_gpx():
        # Failed authentication
        app.logger.debug(f"edit_route(): Refusing permission for '{current_user.email}' and route '{gpx.id}'.")
        Event().log_event("Edit GPX Fail", f"Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    #   Generate Start and Finish maps
    # ----------------------------------------------------------- #
    maps = start_and_end_maps(gpx.filename, gpx_id)

    return render_template("gpx_edit.html", year=current_year, startmap=maps[0], endmap=maps[1], gpx=gpx)


# -------------------------------------------------------------------------------------------------------------- #
# Crop the start of a GPX
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_cut_start', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def gpx_cut_start():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)
    index = request.args.get('index', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"gpx_cut_start(): Missing gpx_id!")
        Event().log_event("Cut Start Fail", f"Missing gpx_id!")
        return abort(400)
    elif not index:
        app.logger.debug(f"gpx_cut_start(): Missing index!")
        Event().log_event("Cut Start Fail", f"Missing index!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)
    index = int(index)

    if not gpx:
        app.logger.debug(f"gpx_cut_start(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Cut Start Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ToDo: Need to check index is valid

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
            or not current_user.can_post_gpx():
        # Failed authentication
        app.logger.debug(f"gpx_cut_start(): Refusing permission for '{current_user.email}' and route '{gpx_id}'.")
        Event().log_event("GPX Cut Start Fail", f"Refusing permission for {current_user.email}, gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Cut start of route
    # ----------------------------------------------------------- #
    cut_start_gpx(gpx.filename, index)

    # ----------------------------------------------------------- #
    # Update GPX for cafes
    # ----------------------------------------------------------- #
    if Gpx().clear_cafe_list(gpx_id):
        # Go ahead and update the list
        flash("Nearby cafe list is being been updated.")
        Thread(target=check_new_gpx_with_all_cafes, args=(gpx_id,)).start()

    else:
        # Should never happen, but...
        app.logger.debug(f"gpx_cut_start(): Failed to clear cafe list, gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Cut Start Fail", f"Failed to clear cafe list, gpx_id = '{gpx_id}'.")
        flash("Sorry, something went wrong!")

    # Back to the edit page
    return redirect(url_for('edit_route', gpx_id=gpx_id))


# -------------------------------------------------------------------------------------------------------------- #
# Crop the start of a GPX
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_cut_end', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def gpx_cut_end():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)
    index = request.args.get('index', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"gpx_cut_end(): Missing gpx_id!")
        Event().log_event("Cut End Fail", f"Missing gpx_id!")
        return abort(400)
    elif not index:
        app.logger.debug(f"gpx_cut_end(): Missing index!")
        Event().log_event("Cut End Fail", f"Missing index!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)
    index = int(index)

    if not gpx:
        app.logger.debug(f"gpx_cut_end(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Cut End Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ToDo: Need to check index is valid

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
            or not current_user.can_post_gpx():
        # Failed authentication
        app.logger.debug(f"gpx_cut_end(): Refusing permission for '{current_user.email}' and route '{gpx_id}'!")
        Event().log_event("GPX Cut End Fail", f"Refusing permission for {current_user.email}, gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Cut end of route
    # ----------------------------------------------------------- #
    cut_end_gpx(gpx.filename, index)

    # ----------------------------------------------------------- #
    # Update GPX for cafes
    # ----------------------------------------------------------- #
    if Gpx().clear_cafe_list(gpx_id):
        # Go ahead and update the list
        flash("Nearby cafe list is being updated...")
        Thread(target=check_new_gpx_with_all_cafes, args=(gpx_id,)).start()
    else:
        # Should never get here, but..
        app.logger.debug(f"gpx_cut_end(): Gpx().clear_cafe_list() failed for gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Cut End Fail", f"Gpx().clear_cafe_list() failed for gpx_id = '{gpx_id}'.")
        flash("Sorry, something went wrong!")

    # Back to the edit page
    return redirect(url_for('edit_route', gpx_id=gpx_id))


# -------------------------------------------------------------------------------------------------------------- #
# Delete a GPX route
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_delete', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def route_delete():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)
    try:
        return_page = request.form['return_page']
    except exceptions.BadRequestKeyError:
        return_page = None
    try:
        confirm = request.form['confirm']
    except exceptions.BadRequestKeyError:
        confirm = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if confirm == "":
        confirm = " "

    print("")
    print("")
    print(f"return_page = '{return_page}'")
    print("")
    print("")

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"route_delete(): Missing gpx_id!")
        Event().log_event("GPX Delete Fail", f"Missing gpx_id!")
        return abort(400)
    elif not confirm:
        app.logger.debug(f"route_delete(): Missing confirm!")
        Event().log_event("GPX Delete Fail", f"Missing confirm!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"route_delete(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Delete Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
            or not current_user.can_post_gpx():
        app.logger.debug(f"route_delete(): Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Delete Fail", f"Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Confirm Delete
    # ----------------------------------------------------------- #
    if confirm != "DELETE":
        app.logger.debug(f"route_delete(): Delete wasn't confirmed, gpx_id = '{gpx_id}', confirm = '{confirm}'!")
        Event().log_event("GPX Delete Fail", f"Delete wasn't confirmed, gpx_id = '{gpx_id}', confirm = '{confirm}'!")
        flash("Delete wasn't confirmed!")
        if return_page:
            return redirect(return_page)

    # ----------------------------------------------------------- #
    # Delete #1: Remove from dB
    # ----------------------------------------------------------- #
    if Gpx().delete_gpx(gpx.id):
        app.logger.debug(f"route_delete(): Success, gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Delete Success", f"Successfully deleted GPX from dB, gpx_id = {gpx_id}!")
        flash("Route was deleted!")
    else:
        # Should never get here, but..
        app.logger.debug(f"route_delete(): Gpx().delete_gpx(gpx.id) failed for gpx.id = '{gpx.id}'.")
        Event().log_event("GPX Delete Fail", f"Gpx().delete_gpx(gpx.id) failed for gpx.id = '{gpx.id}'.")
        flash("Sorry, something went wrong!")
        # Back to GPX list page
        return redirect(url_for('gpx_list'))

    # ----------------------------------------------------------- #
    # Delete #2: Remove GPX file itself
    # ----------------------------------------------------------- #
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))
    try:
        os.remove(filename)
        app.logger.debug(f"route_delete(): File '{filename}' deleted from directory.")
    except Exception as e:
        app.logger.debug(f"route_delete(): Failed to delete GPX file '{filename}', error code was '{e.args}'.")
        Event().log_event("GPX Delete Fail", f"Failed to delete GPX file '{filename}', "
                                             f"error code was {e.args}, gpx_id = {gpx_id}!")

    # Back to GPX list page
    return redirect(url_for('gpx_list'))


# -------------------------------------------------------------------------------------------------------------- #
# Download a GPX route
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_download/<int:gpx_id>', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def route_download(gpx_id):

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"route_download(): Failed to locate GPX with gpx_id = '{gpx_id}' in dB.")
        Event().log_event("GPX Download Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        flash("Sorry, we couldn't find that GPX file in the database!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check GPX file exists
    # ----------------------------------------------------------- #
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))

    if not os.path.exists(filename):
        # Should never get here, but..
        app.logger.debug(f"route_download(): Failed to locate filename = '{filename}', gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Download Fail", f"Failed to locate filename = '{filename}', gpx_id = '{gpx_id}'.")
        flash("Sorry, we couldn't find that GPX file on the server!")
        flash("You should probably fire the web developer...")
        return abort(404)

    # ----------------------------------------------------------- #
    # Update the GPX file with the correct name (in case it's changed)
    # ----------------------------------------------------------- #

    check_route_name(gpx)

    # ----------------------------------------------------------- #
    # Send link to download the file
    # ----------------------------------------------------------- #

    download_name = f"ELSR_{gpx.name.replace(' ','_')}.gpx"

    app.logger.debug(f"route_download(): Serving GPX gpx_id = '{gpx_id}' ({gpx.name}), filename = '{filename}'.")
    Event().log_event("GPX Downloaded", f"Serving GPX gpx_id = '{gpx_id}' ({gpx.name}).")
    return send_from_directory(directory=GPX_UPLOAD_FOLDER_ABS,
                               path=os.path.basename(gpx.filename),
                               download_name=download_name)

