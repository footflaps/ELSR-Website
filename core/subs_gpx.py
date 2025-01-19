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

from core.database.models.cafe_model import CafeModel
from core.database.repositories.gpx_repository import GpxModel, GpxRepository, GPX_ALLOWED_EXTENSIONS
from core.database.repositories.cafe_repository import CafeRepository
from core.database.repositories.event_repository import EventRepository
from core.database.repositories.calendar_repository import CalendarModel, CalendarRepository
from core.subs_email import send_ride_notification_emails

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

def allowed_file(filename: str) -> bool:
    """
    Validate the filename to make sure it has the rig file suffix.
    :param filename:                    GPX filename
    :return:                            True (allowed), False (not allowed)
    """
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in GPX_ALLOWED_EXTENSIONS


# -------------------------------------------------------------------------------------------------------------- #
# Update all GPXes with a new cafe
# -------------------------------------------------------------------------------------------------------------- #

def check_new_cafe_with_all_gpxes(cafe: CafeModel) -> None:
    """
    Called when we add a new cafe to the database. We need to update all GPXModel.cafes_passed JSON strings
    to reference this new cafe if they pass nearby.
    :param cafe:                    Cafe ORM for new cafe
    :return:                        n/a
    """
    app.logger.debug(f"check_new_cafe_with_all_gpxes(): Called with '{cafe.name}'.")

    # Get all the routes
    gpxes: list[GpxModel] = GpxRepository.all_gpxes()

    # Keep a count of how many routes pass this cafe
    routes_passing: int = 0

    # ----------------------------------------------------------- #
    # Loop over each GPX file
    # ----------------------------------------------------------- #
    for gpx in gpxes:

        # Use absolute path for filename
        filename: str = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

        # Check GPX file actually exists
        if os.path.exists(filename):

            # Open the file
            with open(filename, 'r') as file_ref:
                try:
                    gpx_file = gpxpy.parse(file_ref)
                except Exception as e:
                    print(f"Error parsing GPX file '{filename}': {e}")
                    gpx_file = None

            if gpx_file:
                # Max distance
                min_dist_to_cafe_km: float = 100
                dist_along_route_km: float = 0
                saved_dist_along_route_km: float = 1000

                for track in gpx_file.tracks:
                    for segment in track.segments:

                        last_lat = segment.points[0].latitude
                        last_lon = segment.points[0].longitude

                        for point in segment.points:

                            # How far along the route we are
                            dist_along_route_km += mpu.haversine_distance((last_lat, last_lon), (point.latitude, point.longitude))

                            # How far is the cafe from the GPX file
                            dist_to_cafe_km = mpu.haversine_distance((cafe.lat, cafe.lon), (point.latitude, point.longitude))

                            if dist_to_cafe_km < min_dist_to_cafe_km:
                                min_dist_to_cafe_km = dist_to_cafe_km
                                saved_dist_along_route_km = dist_along_route_km

                            last_lat = point.latitude
                            last_lon = point.longitude

                # ----------------------------------------------------------- #
                # Close enough?
                # ----------------------------------------------------------- #
                if min_dist_to_cafe_km <= MIN_DIST_TO_CAFE_KM:
                    app.logger.debug(f"-- Closest to cafe {cafe.name} was {round(min_dist_to_cafe_km, 1)} km"
                                     f" at {round(saved_dist_along_route_km, 1)} km along the route. Total length was {round(dist_along_route_km, 1)} km")
                    GpxRepository.update_cafe_list(
                        gpx_id=gpx.id,
                        cafe_id=cafe.id,
                        dist_to_cafe_km=round(min_dist_to_cafe_km, 1),
                        dist_along_route_km=round(saved_dist_along_route_km, 1)
                    )
                    routes_passing += 1
                else:
                    # Just in case they edited the route and now it doesn't pass this cafe
                    GpxRepository.remove_cafe_from_cafes_passed(gpx_id=gpx.id, cafe_id=cafe.id)

    # ----------------------------------------------------------- #
    # Update cafe
    # ----------------------------------------------------------- #
    cafe.num_routes_passing = routes_passing
    CafeRepository.update_cafe(cafe=cafe)


# -------------------------------------------------------------------------------------------------------------- #
# Remove a cafe from all GPX files
# -------------------------------------------------------------------------------------------------------------- #
def remove_cafe_from_all_gpxes(cafe_id: int) -> None:
    """
    Used when we delete a cafe from the database. We need to remove reference to that cafe from the
    GPXModel.cafes_passed JSON string.
    :param cafe_id:                         ID of the cafe we are deleting
    :return:                                n/a
    """
    app.logger.debug(f"remove_cafe_from_all_gpxes(): Called with cafe_id = '{cafe_id}'.")

    # Get all the routes
    gpxes: list[GpxModel] = GpxRepository.all_gpxes()

    # Loop over each GPX file
    for gpx in gpxes:
        # Remove this entry
        GpxRepository.remove_cafe_from_cafes_passed(gpx_id=gpx.id, cafe_id=cafe_id)


# -------------------------------------------------------------------------------------------------------------- #
# Update a GPX from existing cafe dB
# -------------------------------------------------------------------------------------------------------------- #
def check_new_gpx_with_all_cafes(gpx_id: int, calendar_id: int | None = None) -> None:
    """
    Called when we are adding a new GPX file. We need to update the GPXModel.cafes_passed JSON string
    to contain details of the cafes near to the route.
    :param gpx_id:                      The ID of the GPX ORM in the gpx table
    :param calendar_id:                 If we are sending email alerts then it is the calendar ID of the ride, else None
    :return:
    """
    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx: GpxModel | None = GpxRepository.one_by_id(gpx_id)

    # Make sure gpx_id is valid
    if not gpx:
        app.logger.debug(f"check_new_gpx_with_all_cafes(): Failed to locate GPX: gpx_id = '{gpx_id}'.")
        EventRepository.log_event("GPX Fail", f"Failed to locate GPX: gpx_id = '{gpx_id}'.")
        return

    app.logger.debug(f"check_new_gpx_with_all_cafes(): Updating GPX '{gpx.name}' for closeness to all cafes.")
    EventRepository.log_event("Update GPX", f"Updating GPX '{gpx.name}' for closeness to all cafes.'")

    # ----------------------------------------------------------- #
    # Get all the cafes
    # ----------------------------------------------------------- #
    cafes = CafeRepository.all_cafes()

    # Need a list of closeness
    min_distance_km: list[float] = [100] * len(cafes)
    min_distance_path_km: list[float] = [0] * len(cafes)

    # ----------------------------------------------------------- #
    # Loop over the GPX file
    # ----------------------------------------------------------- #

    # Use absolute path for filename
    filename: str = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

    # Check GPX file actually exists
    if os.path.exists(filename):

        # Open and parse the file
        with open(filename, 'r') as file_ref:

            gpx_file = gpxpy.parse(file_ref)

            for track in gpx_file.tracks:
                for segment in track.segments:

                    # Reset everything
                    last_lat: float = segment.points[0].latitude
                    last_lon: float = segment.points[0].longitude
                    dist_along_route_km: float = 0

                    for point in segment.points:

                        # How far along the route we are
                        dist_along_route_km += mpu.haversine_distance((last_lat, last_lon),
                                                                      (point.latitude, point.longitude))

                        cafe_index: int = 0
                        for cafe in cafes:

                            # How far is the cafe from the GPX file
                            dist_to_cafe_km: float = mpu.haversine_distance((cafe.lat, cafe.lon),
                                                                            (point.latitude, point.longitude))

                            # Is this the closest point, so far, to this cafe?
                            if dist_to_cafe_km < min_distance_km[cafe_index]:
                                # Update our record of the closest point
                                min_distance_km[cafe_index] = dist_to_cafe_km
                                min_distance_path_km[cafe_index] = dist_along_route_km

                            # Next rows in our lists
                            cafe_index += 1

                        # Move along one point
                        last_lat = point.latitude
                        last_lon = point.longitude

            # ----------------------------------------------------------- #
            # Summarise what we found
            # ----------------------------------------------------------- #
            cafe_index = 0
            for cafe in cafes:
                if min_distance_km[cafe_index] <= MIN_DIST_TO_CAFE_KM:
                    app.logger.debug(f"-- Route passes within {round(min_distance_km[cafe_index], 1)} km of {cafe.name} "
                                     f"after {round(min_distance_path_km[cafe_index], 1)} km.")
                    # Push update to GPX file
                    GpxRepository.update_cafe_list(gpx.id, cafe.id, min_distance_km[cafe_index],
                                                   min_distance_path_km[cafe_index])

                # Next rows in our lists
                cafe_index += 1

    # ----------------------------------------------------------- #
    # Have we been asked to send a ride email notification?
    # ----------------------------------------------------------- #
    # send_email is either 'False' for no, or set to an int (ride_id) for yes
    if calendar_id:
        # We have a ride_id index into the calendar
        ride: CalendarModel | None = CalendarRepository.one_by_id(calendar_id)
        # Check that worked
        if not ride:
            # Should never happen, but...
            app.logger.debug(f"check_new_gpx_with_all_cafes(): Passed invalid ride ID, calendar_id = '{calendar_id}'")
            EventRepository.log_event("check_new_gpx_with_all_cafes() Fail", f"Passed invalid ride ID, calendar_id = '{calendar_id}'")
            return
        # Send emails
        send_ride_notification_emails(ride)

# print("Analysing all GPX and all cafes for closeness to each other.")
# with app.app_context():
#     cafes = CafeRepository.all_cafes()
#     for cafe in cafes:
#         print(f"Checking cafe '{cafe.name}'")
#         check_new_cafe_with_all_gpxes(cafe)
