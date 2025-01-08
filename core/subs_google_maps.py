from flask import url_for
import gpxpy
import gpxpy.gpx
import mpu
import os
import json
from datetime import datetime, date


# -------------------------------------------------------------------------------------------------------------- #
# Import app etc from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS, CONFIG_FOLDER, NEW_GOOGLE_MAPS_API_KEY


# -------------------------------------------------------------------------------------------------------------- #
# Import our database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.user_repository import UserRepository, SUPER_ADMIN_USER_ID
from core.database.repositories.cafe_repository import CafeRepository
from core.database.repositories.event_repository import EventRepository
from core.subs_email import send_system_alert_email
from core.subs_sms import send_sms


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# How far we display along the route for trimming start and end
TRIM_DISTANCE_KM = 2.0

# For displaying multiple GPX traces
# based on https://loading.io/color/feature/Spectral-10/
# GPX_COLOURS = ["#9e0142", "#5e4fa2", "#d53e4f", "#3288bd", "#f46d43", "#66c2a5", "#fdae61", "#e6f598"]
# GPX_COLOURS = ["#b30000", "#7c1158", "#4421af", "#1a53ff", "#0d88e6", "#00b7c7", "#5ad45a", "#8be04e", "#ebdc78"]
GPX_COLOURS = ["#b30000", "#7c1158", "#4421af", "#1a53ff", "#0d88e6", "#00b7c7", "#2e2b28", "#e60049", "#dc0ab4"]

# Don't display 100s on a map as total mess
MAX_NUM_GPX_PER_GRAPH = 9

# EL coords
ELSR_HOME = {"lat": 52.199234344363, "lng": 0.113774646436378}

# Google map bounds
MAP_BOUNDS = {
        "north": ELSR_HOME['lat'] + 2,
        "south": ELSR_HOME['lat'] - 2,
        "west": ELSR_HOME['lng'] - 2,
        "east": ELSR_HOME['lng'] + 3,
}

# Maps enable status file location
MAP_STATUS_FILENAME = "map_status.txt"

# Store map counts
MAP_COUNT_FILENAME = "map_counts.csv"

# Map load limits by day
MAP_LIMITS_BY_DAY = {
    "Monday": 1000,
    "Tuesday": 1000,
    "Wednesday": 1000,
    "Thursday": 1000,
    "Friday": 1000,
    "Saturday": 1000,
    "Sunday": 1000,
}

# Map Boost number
MAP_BOOST_NUMBER = 500


# -------------------------------------------------------------------------------------------------------------- #
# Variables
# -------------------------------------------------------------------------------------------------------------- #

maps_boost = {
    'Day': "",
    'Value': 0
}


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Select RGB colour for GPX trace
# -------------------------------------------------------------------------------------------------------------- #

def gpx_colour(number):

    while number >= len(GPX_COLOURS):
        number -= len(GPX_COLOURS)

    return GPX_COLOURS[number]


# -------------------------------------------------------------------------------------------------------------- #
# GPX coordinates (native GoogleMaps variant) for single GPX file
# -------------------------------------------------------------------------------------------------------------- #

def polyline_json(filename):
    # Use absolute path for filename
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(filename))

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
        # Absolute path
        filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

        # File should always be there, but....
        if os.path.exists(filename):

            # Get results for a single GPX file
            tmp = polyline_json(filename)
            name = gpx.name.replace("'", "")
            polyline = {
                'polyline': tmp['polyline'],
                'name': f'<a href="{url_for("gpx_details", gpx_id=gpx.id)}">Route: {name}</a>',
                'color': gpx_colour(num_routes),
            }

            # Add to our set
            polyline_set.append(polyline)
            mid_lat += tmp['midlat']
            mid_lon += tmp['midlon']
            num_routes += 1

        if num_routes >= MAX_NUM_GPX_PER_GRAPH:
            break

    # Avoid /0
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
        if CafeRepository().one_by_id(cafe_summary["id"]).active:
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

def start_and_end_maps_native_gm(filename, gpx_id, return_path):
    # Use absolute path for filename
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(filename))

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
                            "title": f'<a href="{url_for("gpx_cut_start", gpx_id=gpx_id, index=index, return_path=f"{return_path}")}">Start Here! (Point {index})</a>',
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
                            "title": f'<a href="{url_for("gpx_cut_end", gpx_id=gpx_id, index=index, return_path=f"{return_path}")}">Finish Here! (Point {index})</a>',
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
# Are maps enabled?
# -------------------------------------------------------------------------------------------------------------- #
def maps_enabled():
    # ----------------------------------------------------------- #
    #   Read status from file
    # ----------------------------------------------------------- #
    filename = os.path.join(CONFIG_FOLDER, os.path.basename(MAP_STATUS_FILENAME))

    # Better check file is there
    if not os.path.exists(filename):
        # Create it disabled just to be safe
        app.logger.error(f"maps_enabled(): Missing file '{filename}'. Created new one.")
        EventRepository().log_event("maps_enabled()", f"Missing file '{filename}'. Created new one.")
        with open(filename, 'w') as file:
            file.write("False")

    with open(filename, 'r') as file:
        text = file.readline().strip()
        map_status = text == "True"

    return map_status


# -------------------------------------------------------------------------------------------------------------- #
# API Key for Google maps
# -------------------------------------------------------------------------------------------------------------- #
def google_maps_api_key():
    if maps_enabled():
        return NEW_GOOGLE_MAPS_API_KEY
    else:
        # 'None' tells Jinja to show a jpg of a Google Map with a message saying
        # 'Live maps are temporally disabled'
        return None

# -------------------------------------------------------------------------------------------------------------- #
# Enable maps
# -------------------------------------------------------------------------------------------------------------- #
def set_enable_maps():
    # ----------------------------------------------------------- #
    #   Write status to file
    # ----------------------------------------------------------- #
    filename = os.path.join(CONFIG_FOLDER, os.path.basename(MAP_STATUS_FILENAME))

    with open(filename, 'w') as file:
        file.write("True")

    # ----------------------------------------------------------- #
    #   Alert Super Admin
    # ----------------------------------------------------------- #
    # Email alert
    send_system_alert_email("Maps have been enabled.")

    # SMS Alert
    site_owner = UserRepository().one_by_id(SUPER_ADMIN_USER_ID)
    send_sms(site_owner, "Maps have been enabled")


# -------------------------------------------------------------------------------------------------------------- #
# Disable maps
# -------------------------------------------------------------------------------------------------------------- #
def set_disable_maps():
    # ----------------------------------------------------------- #
    #   Set disabled
    # ----------------------------------------------------------- #
    filename = os.path.join(CONFIG_FOLDER, os.path.basename(MAP_STATUS_FILENAME))

    with open(filename, 'w') as file:
        file.write("False")

    # ----------------------------------------------------------- #
    #   Alert Super Admin
    # ----------------------------------------------------------- #
    # Email alert
    send_system_alert_email("Maps have been disabled.")

    # SMS Alert
    site_owner = UserRepository().one_by_id(SUPER_ADMIN_USER_ID)
    send_sms(site_owner, "Maps have been disabled")


# -------------------------------------------------------------------------------------------------------------- #
# Return map limit for the day
# -------------------------------------------------------------------------------------------------------------- #
def map_limit_by_day(day: str) -> int:

    print(f"map_limit_by_day: maps_boost = {maps_boost}")

    # This is the baseline number
    limit: int = MAP_LIMITS_BY_DAY[day]
    print(f"Default limit is '{limit}'")
    print(maps_boost)

    # Are we boosting?
    if maps_boost['Day'] == day:
        limit += maps_boost['Value']

    return limit


# -------------------------------------------------------------------------------------------------------------- #
# Boost map limit (until midnight)
# -------------------------------------------------------------------------------------------------------------- #
def boost_map_limit():
    global maps_boost

    # Get today as string eg "Monday"
    today_str = datetime.today().strftime("%A")

    # Make sure Day is set to today
    if maps_boost['Day'] == today_str:
        # Day is the same, so just increment the boost
        maps_boost['Value'] += MAP_BOOST_NUMBER
    else:
        # Different day, so reset
        maps_boost['Day'] = today_str
        maps_boost['Value'] = MAP_BOOST_NUMBER

    # ----------------------------------------------------------- #
    #   Alert Super Admin
    # ----------------------------------------------------------- #
    # Email alert
    send_system_alert_email("Map boost has been applied.")

    # SMS Alert
    site_owner = UserRepository().one_by_id(SUPER_ADMIN_USER_ID)
    send_sms(site_owner, "Map boost has been applied")


# -------------------------------------------------------------------------------------------------------------- #
# Keep a count of map loads
# -------------------------------------------------------------------------------------------------------------- #
def count_map_loads(count: int):
    # ----------------------------------------------------------- #
    #   Need today's date
    # ----------------------------------------------------------- #
    today_str = datetime.today().strftime("%Y%m%d")

    # ----------------------------------------------------------- #
    #   Read in the whole file
    # ----------------------------------------------------------- #
    # Use abs path
    filename = os.path.join(CONFIG_FOLDER, os.path.basename(MAP_COUNT_FILENAME))

    # Make sure file exists!
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            lines = file.readlines()
    else:
        app.logger.error(f"count_map_loads(): Missing file '{filename}'.")
        EventRepository().log_event("count_map_loads()", f"Missing file '{filename}'.")
        lines = []

    # ----------------------------------------------------------- #
    #   Modify file to include count
    # ----------------------------------------------------------- #
    if len(lines) > 0:
        last_line = lines[-1]
    else:
        last_line = ""

    # Does the last line cover today?
    if last_line.split(',')[0].strip() == today_str:
        # Increment count
        total_today = int(last_line.split(',')[1]) + count
        # Update last line
        lines[-1] = f"{today_str},{total_today}\n"
    else:
        # Must have rolled over to new day
        total_today = count
        lines.append(f"{today_str},{total_today}\n")
        # Reset boost, as it's a new day
        print("Resetting maps_boost!")
        maps_boost['Day'] = ""
        maps_boost['Value'] = 0

    # ----------------------------------------------------------- #
    #   Write file back out
    # ----------------------------------------------------------- #
    with open(filename, 'w') as file:
        file.writelines(lines)

    # ----------------------------------------------------------- #
    #   Compare against our thresholds
    # ----------------------------------------------------------- #
    today_str = datetime.today().strftime("%A")
    map_limit = map_limit_by_day(today_str)

    # Exceeded target for the day?
    if total_today > map_limit:
        if maps_enabled():
            # Disable maps
            app.logger.debug(f"count_map_loads(): Disabling maps as count is {total_today} / {map_limit}!")
            EventRepository().log_event("Map Load Count", f"Disabling maps as count is {total_today} / {map_limit}!")
            set_disable_maps()
        else:
            # Already disabled
            app.logger.debug(f"count_map_loads(): Maps have already been disabled, "
                             f"as count is {total_today} / {map_limit}!")


# -------------------------------------------------------------------------------------------------------------- #
# Get current count
# -------------------------------------------------------------------------------------------------------------- #
def get_current_map_count():
    global maps_boost

    # ----------------------------------------------------------- #
    #   Need today's date
    # ----------------------------------------------------------- #
    today_str = datetime.today().strftime("%Y%m%d")

    # ----------------------------------------------------------- #
    #   Read in the whole file
    # ----------------------------------------------------------- #
    # Use abs path
    filename = os.path.join(CONFIG_FOLDER, os.path.basename(MAP_COUNT_FILENAME))

    # Make sure file exists!
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            lines = file.readlines()
    else:
        app.logger.error(f"get_current_map_count(): Missing file '{filename}'.")
        EventRepository().log_event("get_current_map_count()", f"Missing file '{filename}'.")
        lines = []

    # ----------------------------------------------------------- #
    #   Need last line
    # ----------------------------------------------------------- #
    if len(lines) > 0:
        last_line = lines[-1]
    else:
        last_line = ""

    # Does the last line cover today?
    if last_line.split(',')[0].strip() == today_str:
        # Use this number
        total_today = int(last_line.split(',')[1])
    else:
        # Must have rolled over to new day
        total_today = 0

    # Return today's count
    return total_today


# -------------------------------------------------------------------------------------------------------------- #
# Generate graph of maps counts vs cap
# -------------------------------------------------------------------------------------------------------------- #
def graph_map_counts():
    # ----------------------------------------------------------- #
    #   Read in the whole map usage file
    # ----------------------------------------------------------- #
    # Use abs path
    filename = os.path.join(CONFIG_FOLDER, os.path.basename(MAP_COUNT_FILENAME))

    # Make sure file exists!
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            lines = file.readlines()
    else:
        return None

    # ----------------------------------------------------------- #
    #   Need three arrays
    # ----------------------------------------------------------- #
    dates = []
    counts = []
    limits = []

    # ----------------------------------------------------------- #
    #   Generate our map count data sets
    # ----------------------------------------------------------- #
    for line in lines:
        try:
            # Get date and number map reads
            line = line.rstrip('\n')
            data = line.split(',')

            # Need the day of week
            date_str = data[0].strip()
            date_obj = date(int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]))
            day_of_week = date_obj.strftime('%A')

            # Need map count
            count = int(data[1])

            # Need limit by day of week
            limit = MAP_LIMITS_BY_DAY[day_of_week]

            # Stick in our lists
            dates.append(date_str)
            counts.append(count)
            limits.append(limit)
        except Exception as e:
            pass

    # ----------------------------------------------------------- #
    #   Return all
    # ----------------------------------------------------------- #
    return {"dates": dates,
            "counts": counts,
            "limits": limits}


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Start of day record in the logfile / console etc
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

print(f"Maps Status = {maps_enabled()}, current map count = {get_current_map_count()}")
app.logger.debug(f"Start of day: Maps Status = {maps_enabled()}, current map count = {get_current_map_count()}")
EventRepository().log_event("Start of day:", f"Maps Status = {maps_enabled()}, current map count = {get_current_map_count()}")
