import random
from flask import url_for
from flask_googlemaps import Map
import gpxpy
import gpxpy.gpx
import mpu
import os
from time import sleep
from datetime import datetime, timedelta
import json

# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_gpx import Gpx, GPX_ALLOWED_EXTENSIONS
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

# For displaying multiple GPX traces
#               Red        Blue      Black      Green      Fuschia    Maroon     Yellow     Lime       Aqua
#               Purple     Navy      Teal       Olive      Grey
GPX_COLOURS = ["#FF0000", "#0000FF", "#000000", "#008000", "#FF00FF", "#800000", "#FFFF00", "#00FF00", "#00FFFF",
               "#800080", "#000080", "#008080", "#808000", "#808080"]

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
                app.logger.debug(f"-- Route passes within {round(min_distance_km[cafe.id - 1], 1)} km of {cafe.name} "
                                 f"after {round(min_distance_path_km[cafe.id - 1], 1)} km.")
                # Push update to GPX file
                Gpx().update_cafe_list(gpx.id, cafe.id, min_distance_km[cafe.id - 1],
                                       min_distance_path_km[cafe.id - 1])


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
# GPX coordinates (native GoogleMaps variant) for single GPX file
# -------------------------------------------------------------------------------------------------------------- #

def polyline_json(filename):
    # Use absolute path for filename
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(filename)))

    # This is the list we will return
    polyline = []

    # Also need mid lat and min lon
    mid_lat = 0
    mid_lon = 0
    num_points = 0

    with open(filename, 'r') as gpx_file:

        gpx_track = gpxpy.parse(gpx_file)

        for track in gpx_track.tracks:
            for segment in track.segments:

                for point in segment.points:
                    polyline.append({
                        'lat': point.latitude,
                        'lng': point.longitude
                    })

                    mid_lat += point.latitude
                    mid_lon += point.longitude
                    num_points += 1

    # Required format is a string with no quotes:
    # const    flightPlanCoordinates = [
    #     {lat: 37.772, lng: -122.214},
    #     {lat: 21.291, lng: -157.821},
    #     {lat: -18.142, lng: 178.431},
    #     {lat: -27.467, lng: 153.027},
    # ];

    return {
        'polyline': json.dumps(polyline).replace('"', ''),
        'midlat': mid_lat / num_points,
        'midlon': mid_lon / num_points,
    }


# -------------------------------------------------------------------------------------------------------------- #
# Markers for a set of routes
# -------------------------------------------------------------------------------------------------------------- #

def create_polyline_set(gpxes):
    # This is what we return
    polyline_set = []

    # Need to average out the routes
    mid_lat = 0
    mid_lon = 0
    num_routes = 0

    for gpx in gpxes:
        filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))
        if os.path.exists(filename):
            tmp = polyline_json(filename)
            polyline = {
                'polyline': tmp['polyline'],
                'name': gpx.name,
                'color': GPX_COLOURS[num_routes % len(GPX_COLOURS)],
            }
            polyline_set.append(polyline)
            mid_lat += tmp['midlat']
            mid_lon += tmp['midlon']
            num_routes += 1

    if num_routes > 0:
        return {
            'polylines': polyline_set,
            'midlat': mid_lat / num_routes,
            'midlon': mid_lon / num_routes,
        }
    else:
        return {
            'polylines': [],
            'midlat': 0,
            'midlon': 0,
        }


# -------------------------------------------------------------------------------------------------------------- #
# Markers for a set of cafes (native Google Map variant)
# -------------------------------------------------------------------------------------------------------------- #

def markers_for_cafes_native(cafes):
    markers = []
    for cafe_summary in cafes:

        # Need to look up current cafe open / closed status
        if Cafe().one_cafe(cafe_summary["id"]).active:
            icon_colour = '#2196f3'
        else:
            icon_colour = '#ff0000'

        markers.append({
            "position": {"lat": cafe_summary['lat'], "lng": cafe_summary['lon']},
            "title": f'<a href="{url_for("cafe_details", cafe_id=cafe_summary["id"])}">{cafe_summary["name"]}</a>',
            "color": icon_colour
        })

    return markers


# -------------------------------------------------------------------------------------------------------------- #
# Edit Map Start and Finish Map Points for Native Google Maps
# -------------------------------------------------------------------------------------------------------------- #

def start_and_end_maps_native_gm(filename, gpx_id):
    # Use absolute path for filename
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(filename)))

    # Creating two separate maps:
    start_markers = []
    end_markers = []

    # Where we will centre the start map
    start_lat = 0
    start_lon = 0
    num_start_points = 0

    # Where we will centre the end map
    end_lat = 0
    end_lon = 0
    num_end_points = 0

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
                            "position": {"lat": point.latitude, "lng": point.longitude},
                            "title": f'<a href="{url_for("gpx_cut_start", gpx_id=gpx_id, index=index)}">Start Here! (Point {index})</a>',
                        })

                        start_lat += point.latitude
                        start_lon += point.longitude
                        num_start_points += 1

                    else:
                        break

                    last_lat = point.latitude
                    last_lon = point.longitude

        if num_start_points > 0:
            start_map_coords = {"lat": start_lat / num_start_points, "lng": start_lon / num_start_points}
        else:
            start_map_coords = {"lat": 0, "lng": 0}

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
                            "position": {"lat": point.latitude, "lng": point.longitude},
                            "title": f'<a href="{url_for("gpx_cut_end", gpx_id=gpx_id, index=index)}">Finish Here! (Point {index})</a>',
                        })

                        end_lat += point.latitude
                        end_lon += point.longitude
                        num_end_points += 1

                    else:
                        break

                    last_lat = point.latitude
                    last_lon = point.longitude
                    index -= 1

            if num_end_points > 0:
                end_map_coords = {"lat": end_lat / num_end_points, "lng": end_lon / num_end_points}
            else:
                end_map_coords = {"lat": 0, "lng": 0}

    return [start_markers, start_map_coords, end_markers, end_map_coords]


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
