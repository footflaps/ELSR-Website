import math
import numpy
import os
import gpxpy
import gpxpy.gpx
import mpu


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS
from core.dB_events import Event


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Maximum distance we allow between start and finish to consider route circular
MAX_CIRCULAR_DELTA_KM = 10.0


# -------------------------------------------------------------------------------------------------------------- #
# Work out if a route is Clockwise or anti-Clockwise
# -------------------------------------------------------------------------------------------------------------- #
def gpx_direction(gpx_filename, gpx_id):
    # ----------------------------------------------------------- #
    # Check we have an actual file
    # ----------------------------------------------------------- #

    # Use absolute path for filename
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx_filename))

    # Check GPX file actually exists
    if not os.path.exists(filename):
        app.logger.debug(f"gpx_direction(): Failed to locate file: gpx_id = '{gpx_id}'.")
        Event().log_event("gpx_direction Fail", f"Failed to locate file: gpx_id = '{gpx_id}'.")
        return "Missing File"

    # ----------------------------------------------------------- #
    # Work out the direction the route goes in
    # ----------------------------------------------------------- #

    # Open and parse the file
    with open(filename, 'r') as file_ref:

        gpx_file = gpxpy.parse(file_ref)

        for track in gpx_file.tracks:
            for segment in track.segments:

                # We'll need these
                start_lat = segment.points[0].latitude
                start_lon = segment.points[0].longitude
                app.logger.debug(f"start_lat = '{start_lat}', start_lon = '{start_lon}'")

                num_points = len(segment.points)

                # Outward point is 25% along the path
                out_lat = segment.points[math.floor(num_points*0.25)].latitude
                out_lon = segment.points[math.floor(num_points*0.25)].longitude
                app.logger.debug(f"out_lat = '{out_lat}', out_lon = '{out_lon}'")

                # Return point is 75% along the path
                ret_lat = segment.points[math.floor(num_points * 0.75)].latitude
                ret_lon = segment.points[math.floor(num_points * 0.75)].longitude
                app.logger.debug(f"ret_lat = '{ret_lat}', ret_lon = '{ret_lon}'")

                # Last point
                last_lat = segment.points[-1].latitude
                last_lon = segment.points[-1].longitude
                app.logger.debug(f"last_lat = '{last_lat}', last_lon = '{last_lon}'")

    # ----------------------------------------------------------- #
    # Derive angle of two vectors
    # ----------------------------------------------------------- #
    return cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, last_lat, last_lon, False)


def cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, last_lat, last_lon, debug):
    # ----------------------------------------------------------- #
    # Check for circular route
    # ----------------------------------------------------------- #
    dist_km = mpu.haversine_distance((last_lat, last_lon), (start_lat, start_lon))
    if dist_km > MAX_CIRCULAR_DELTA_KM:
        # Not circular, so can't derive CW / ACW
        return "Not Circular"

    # ----------------------------------------------------------- #
    # Derive angle of two vectors
    # ----------------------------------------------------------- #
    outward_angle_deg = numpy.arctan2(out_lat - start_lat, out_lon - start_lon) / math.pi * 180
    return_angle_deg = numpy.arctan2(ret_lat - start_lat, ret_lon - start_lon) / math.pi * 180

    if debug:
        print(f"outward_angle_deg = '{round( outward_angle_deg, 3)}', return_angle_deg = '{round(return_angle_deg, 3)}'")

    # ----------------------------------------------------------- #
    # We have to cope with two exceptions, the vectors spanning 180/-180
    # ----------------------------------------------------------- #
    if outward_angle_deg > 90 and \
            return_angle_deg < -90:
        return_angle_deg += 360

    if return_angle_deg > 90 and \
            outward_angle_deg < -90:
        outward_angle_deg += 360

    # ----------------------------------------------------------- #
    # Make them both +ve
    # ----------------------------------------------------------- #
    if outward_angle_deg > return_angle_deg:
        return "CW"
    else:
        return "CCW"


def test_cw_ccw():
    start_lon = 52.2
    start_lat = 0.11
    range_deg = 0.2

    # 0 deg = due North, 90 deg = due East
    for deg in range(-90, 391, 10):
        out_deg = deg
        ret_deg = deg - 20

        out_lat = start_lat + math.sin(out_deg/180 * math.pi) * range_deg
        out_lon = start_lon + math.cos(out_deg/180 * math.pi) * range_deg
        ret_lat = start_lat + math.sin(ret_deg / 180 * math.pi) * range_deg
        ret_lon = start_lon + math.cos(ret_deg / 180 * math.pi) * range_deg

        if cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, start_lon, start_lat, False) == "CW":
            pass
        else:
            print("CW FAIL")
            print(f"deg = '{deg}'")
            print(f"out_deg = '{out_deg}': out_lon = '{round(out_lon, 3)}', out_lat = '{round(out_lat, 3)}'")
            print(f"ret_deg = '{ret_deg}': ret_lon = '{round(ret_lon, 3)}',ret_lat = '{round(ret_lat, 3)}'")
            cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, start_lon, start_lat, True)

    for deg in range(-90, 391, 10):
        out_deg = deg
        ret_deg = deg + 20

        out_lat = start_lat + math.sin(out_deg / 180 * math.pi) * range_deg
        out_lon = start_lon + math.cos(out_deg / 180 * math.pi) * range_deg
        ret_lat = start_lat + math.sin(ret_deg / 180 * math.pi) * range_deg
        ret_lon = start_lon + math.cos(ret_deg / 180 * math.pi) * range_deg

        if cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, start_lon, start_lat, False) == "CCW":
            pass
        else:
            print("CCW FAIL")
            print(f"deg = '{deg}'")
            print(f"out_deg = '{out_deg}': out_lon = '{round(out_lon, 3)}', out_lat = '{round(out_lat, 3)}'")
            print(f"ret_deg = '{ret_deg}': ret_lon = '{round(ret_lon, 3)}',ret_lat = '{round(ret_lat, 3)}'")
            cw_or_ccw(start_lon, start_lat, out_lat, out_lon, ret_lat, ret_lon, start_lon, start_lat, True)

# test_cw_ccw()
