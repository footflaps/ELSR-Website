import gpxpy
import gpxpy.gpx
import mpu


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
