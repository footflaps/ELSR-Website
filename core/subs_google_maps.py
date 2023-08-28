from flask import url_for
import gpxpy
import gpxpy.gpx
import mpu
import os
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app etc from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import GPX_UPLOAD_FOLDER_ABS


# -------------------------------------------------------------------------------------------------------------- #
# Import our database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Note: Key is domain restricted to *.elsr.co.uk
GOOGLE_MAPS_API_KEY = os.environ['ELSR_GOOGLE_MAPS_API_KEY']

# How far we display along the route for trimming start and end
TRIM_DISTANCE_KM = 2.0

# For displaying multiple GPX traces
# based on https://loading.io/color/feature/Spectral-10/
GPX_COLOURS = ["#9e0142", "#5e4fa2", "#d53e4f", "#3288bd", "#f46d43", "#66c2a5", "#fdae61", "#e6f598"]

# Don't display 100s on a map as total mess
MAX_NUM_GPX_PER_GRAPH = 10

# EL coords
ELSR_HOME = {"lat": 52.203292, "lng": 0.131839}

# Google map bounds
MAP_BOUNDS = {
        "north": ELSR_HOME['lat'] + 0.5,
        "south": ELSR_HOME['lat'] - 0.5,
        "west": ELSR_HOME['lng'] - 1,
        "east": ELSR_HOME['lng'] + 1,
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

        if num_routes > MAX_NUM_GPX_PER_GRAPH:
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

