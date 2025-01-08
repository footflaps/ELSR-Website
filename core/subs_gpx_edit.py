import random
import gpxpy
import gpxpy.gpx
import mpu
import os
from time import sleep
from datetime import datetime, timedelta


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.gpx_repository import GpxRepository, GPX_ALLOWED_EXTENSIONS
from core.database.repositories.cafe_repository import CafeRepository
from core.database.repositories.event_repository import EventRepository


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Remove any points closer together than this
GPX_MAX_RESOLUTION_KM = 0.05


# -------------------------------------------------------------------------------------------------------------- #
# Update existing file
# -------------------------------------------------------------------------------------------------------------- #

def update_existing_gpx(gpx_file, gpx_filename):
    # This is the full path to the existing GPX file we are going to over write
    old_filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx_filename))

    # This is a temp file we will use to write out the new GPX file to first
    tmp_filename = f"{old_filename}.tmp"

    # ----------------------------------------------------------- #
    # Step 1: Wait for tmp file to clear
    # ----------------------------------------------------------- #
    # As Gunicorn has multiple workers, it is possible (and has happened) that two workers call this function
    # overlapping in time and they corrupt each other's files. What actually seems to happen is one user reloads the
    # page rapidly, and we end up in a 'right mess'.

    # Wait for the tmp file to get removed by the 'other' version of this function
    for _ in range(0, 20):
        if os.path.exists(tmp_filename):
            app.logger.debug(f"update_existing_gpx(): Detected '{tmp_filename}', so sleeping for 1 second.")
            sleep(1)
        else:
            break

    # If it's still there after 20 seconds, just blow it away
    if os.path.exists(tmp_filename):
        app.logger.debug(f"update_existing_gpx(): '{tmp_filename}' still there after 20 secs, so deleting.")
        try:
            os.remove(tmp_filename)
            # We need this as remove seems to keep the file locked for a short period
            sleep(0.5)
        except Exception as e:
            app.logger.debug(f"update_existing_gpx(): Failed to delete existing file '{tmp_filename}', "
                             f"error code was '{e.args}'.")
            EventRepository.log_event("GPX Fail",
                              f"Failed to delete existing file '{tmp_filename}', error code was '{e.args}'.")
            return False

    # ----------------------------------------------------------- #
    # Step 2: Write out our new file to "gpx_XXX.gpx.tmp"
    # ----------------------------------------------------------- #
    try:
        with open(tmp_filename, 'w') as file_ref2:
            file_ref2.write(gpx_file.to_xml())
    except Exception as e:
        EventRepository.log_event("GPX Fail", f"Failed to write file '{tmp_filename}', error code was '{e.args}'.")
        app.logger.debug(f"update_existing_file: Failed to write file '{tmp_filename}', error code was '{e.args}'.")
        return False

    # ----------------------------------------------------------- #
    # Step 3: Delete the original file "gpx_XXX.gpx"
    # ----------------------------------------------------------- #
    try:
        os.remove(old_filename)
        # We need this as remove seems to keep the file locked for a short period
        sleep(0.5)
    except Exception as e:
        EventRepository.log_event("GPX Fail", f"Failed to delete existing file '{old_filename}', error code was '{e.args}'.")
        app.logger.debug(f"update_existing_file: Failed to delete existing file '{old_filename}', "
                         f"error code was '{e.args}'.")
        return False

    # ----------------------------------------------------------- #
    # Step 4: Rename "gpx_XXX.gpx.tmp" --> "gpx_XXX.gpx"
    # ----------------------------------------------------------- #
    try:
        os.rename(tmp_filename, old_filename)
    except Exception as e:
        EventRepository.log_event("GPX Fail", f"Failed to rename existing file '{tmp_filename}', error code was '{e.args}'.")
        app.logger.debug(f"update_existing_file: Failed to rename existing file '{tmp_filename}', "
                         f"error code was '{e.args}'.")
        return False

    # All worked if we get here!
    return True


# -------------------------------------------------------------------------------------------------------------- #
# Cut the end of the start of the GPX
# -------------------------------------------------------------------------------------------------------------- #

def cut_start_gpx(gpx_filename, start_count):
    EventRepository.log_event("GPX cut Start", f"Called with gpx_filename='{gpx_filename}', start_count='{start_count}'.")
    app.logger.debug(f"cut_start_gpx: Called with gpx_filename='{gpx_filename}', start_count='{start_count}'.")

    # ----------------------------------------------------------- #
    # Open the file and trim it
    # ----------------------------------------------------------- #

    # Use absolute path for filename
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx_filename))

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
    EventRepository.log_event("GPX cut Start", f"Length was {count_before}, now {count_after}. gpx_filename = '{gpx_filename}'")
    app.logger.debug(f"cut_start_gpx: Length was {count_before}, now {count_after}. gpx_filename = '{gpx_filename}'")


# -------------------------------------------------------------------------------------------------------------- #
# Crop the end of the GPX file
# -------------------------------------------------------------------------------------------------------------- #
def cut_end_gpx(gpx_filename, end_count):
    EventRepository.log_event("GPX cut End", f"Called with gpx_filename='{gpx_filename}', end_count='{end_count}'.")
    app.logger.debug(f"cut_end_gpx: Called with gpx_filename='{gpx_filename}', end_count='{end_count}'.")

    # ----------------------------------------------------------- #
    # Open the file and trim it
    # ----------------------------------------------------------- #
    # Use absolute path for filename
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx_filename))

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
    EventRepository.log_event("GPX cut End", f"Length was {count_before}, now {count_after}. gpx_filename = '{gpx_filename}'.")
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
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

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
# Clean up the GPX file and update length / elevation stats in the db
# -------------------------------------------------------------------------------------------------------------- #

def strip_excess_info_from_gpx(gpx_filename, gpx_id, route_name):
    # ----------------------------------------------------------- #
    # Header
    # ----------------------------------------------------------- #
    app.logger.debug(f"strip_excess_info_from_gpx(): Called with gpx_filename='{gpx_filename}', gpx_id='{gpx_id}'.")

    # ----------------------------------------------------------- #
    # Use absolute path
    # ----------------------------------------------------------- #
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx_filename))

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
    GpxRepository.update_stats(gpx_id, total_length_km, total_ascent_m)

    # ----------------------------------------------------------- #
    # Overwrite the existing file
    # ----------------------------------------------------------- #
    update_existing_gpx(new_gpx_file, gpx_filename)
    EventRepository.log_event("Clean GPX", f"Culled from {num_points_before} to {num_points_after} points.")
    app.logger.debug(f"strip_excess_info_from_gpx(): Culled from {num_points_before} to {num_points_after} points.")

