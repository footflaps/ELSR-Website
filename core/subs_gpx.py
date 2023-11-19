import gpxpy
import gpxpy.gpx
import mpu
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_gpx import Gpx, GPX_ALLOWED_EXTENSIONS
from core.dB_cafes import Cafe
from core.dB_events import Event
from core.db_calendar import Calendar
from core.subs_email_sms import send_ride_notification_emails


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
        filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

        # Check GPX file actually exists
        if os.path.exists(filename):

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
# Remove a cafe from all GPX files
# -------------------------------------------------------------------------------------------------------------- #
def remove_cafe_from_all_gpxes(cafe_id):
    app.logger.debug(f"remove_cafe_from_all_gpxes(): Called with cafe_id = '{cafe_id}'.")

    # Get all the routes
    gpxes = Gpx().all_gpxes()

    # Loop over each GPX file
    for gpx in gpxes:
        # Remove this entry
        Gpx().remove_cafe_list(gpx.id, cafe_id)


# -------------------------------------------------------------------------------------------------------------- #
# Update a GPX from existing cafe dB
# -------------------------------------------------------------------------------------------------------------- #

def check_new_gpx_with_all_cafes(gpx_id: int, send_email):
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
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

    # Check GPX file actually exists
    if os.path.exists(filename):

        # Open and parse the file
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

    # ----------------------------------------------------------- #
    # Have we been asked to send a ride email notification?
    # ----------------------------------------------------------- #
    # send_email is either 'False' for no, or set to an int (ride_id) for yes
    if type(send_email) == int:
        # We have a ride_id index into the calendar
        ride = Calendar().one_ride_id(send_email)
        # Check that worked
        if not ride:
            # Should never happen, but...
            app.logger.debug(f"check_new_gpx_with_all_cafes(): Passed invalid ride ID, send_email = '{send_email}'")
            Event().log_event("check_new_gpx_with_all_cafes() Fail", f"Passed invalid ride ID, send_email = '{send_email}'")
            return
        # Send emails
        send_ride_notification_emails(ride)







