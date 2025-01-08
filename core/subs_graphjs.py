import gpxpy
import gpxpy.gpx
import mpu
import os


from core import GPX_UPLOAD_FOLDER_ABS
from core.subs_google_maps import gpx_colour
from core.database.repositories.cafe_repository import CafeRepository


# -------------------------------------------------------------------------------------------------------------- #
# Constants used to verify sensible cafe coordinates
# -------------------------------------------------------------------------------------------------------------- #

# Map icon
# The icon gets located by its centre, but really needs to have it's lower point sat on the line,
# so frig this by moving it up a bit.
FUDGE_FACTOR_m = 10


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Extract a super set of elevation data
# -------------------------------------------------------------------------------------------------------------- #

def get_elevation_data_set(gpxes):
    # This is what we will return
    super_set = []
    index = 0

    for gpx in gpxes:

        # This is the absolute path to the file
        filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

        # Check the file exists as you never know..
        if os.path.exists(filename):
            # Generate one set
            super_set.append({
                'elevation': get_elevation_data(filename),
                'colour': gpx_colour(index),
            })

            # Next route
            index += 1

    return super_set


# -------------------------------------------------------------------------------------------------------------- #
# Extract the data set of elevations for graph JS
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

def get_cafe_heights_from_gpx(cafe_list, elevation_data):
    # This is what we will return
    cafe_elevation_data = []

    # NB The cafe list is a JSON string from the gpx object
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
# Generate icons for the cafes which match route elevation
# -------------------------------------------------------------------------------------------------------------- #

def get_destination_cafe_height(elevation_data_set, gpx_set, cafe_set):
    # This is what we will return
    cafe_elevation_data = []

    # Loop through each route
    for n in range(0, len(elevation_data_set)):

        elevation_data = elevation_data_set[n]
        gpx = gpx_set[n]
        target_cafe = cafe_set[n]

        cafe_list: list[dict] = CafeRepository.cafes_passed_by_gpx(gpx.cafes_passed)

        # NB The cafe list is a JSON string from the gpx object
        for cafe in cafe_list:
            # Extract the name and distance
            cafe_id = cafe['id']
            cafe_name = cafe['name']
            cafe_dist = float(cafe['range_km'])

            # Find closest point in terms of distance along the route and then
            # use the elevation of that point for the cafe icon.
            closet_km = 100
            elevation = 0

            # Now find elevation...
            for point in elevation_data['elevation']:

                # Delta between distance along route of this point and our cafe's distance along the route
                delta_km = abs(float(point['x']) - cafe_dist)
                if delta_km < closet_km:
                    # New closest point
                    closet_km = delta_km
                    elevation = point['y']

            # Have all we need for this cafe's entry
            if cafe_id == target_cafe.id:
                cafe_elevation_data.append({
                    'name': cafe_name,
                    'coord':
                        {
                            'x': cafe_dist,
                            'y': elevation + FUDGE_FACTOR_m
                        }
                })

    return cafe_elevation_data
