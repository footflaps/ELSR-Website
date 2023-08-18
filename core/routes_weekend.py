from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import date
from werkzeug import exceptions
import mpu
import os
from threading import Thread


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe, CreateCafeForm, OPEN_CAFE_COLOUR, CLOSED_CAFE_COLOUR
from core.dB_cafe_comments import CafeComment, CreateCafeCommentForm
from core.subs_gpx import check_new_cafe_with_all_gpxes
from core.subs_google_maps import create_polyline_set, MAX_NUM_GPX_PER_GRAPH, ELSR_HOME, MAP_BOUNDS, GOOGLE_MAPS_API_KEY
from core.dB_gpx import Gpx
from core.db_messages import Message, ADMIN_EMAIL
from core.dB_events import Event
from core.db_users import User, update_last_seen, logout_barred_user
from core.send_emails import alert_admin_via_sms
from core.subs_cafe_photos import update_cafe_photo


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Weekend ride list
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/weekend', methods=['GET'])
@update_last_seen
def calendar():
    # -------------------------------------------------------------------------------------------- #
    # Show the schedule of rides
    # -------------------------------------------------------------------------------------------- #

    saturday = "Saturday Aug 19 2023"
    sunday = "Sunday Aug 20 2023"

    saturday_rides = [
        {"group": "Decaff",
         "leader": "Anna",
         "destination": "Buntingford",
         "distance": 96,
         "elevation": 672
         },
        {"group": "Espresso",
         "leader": "Andy Linney",
         "destination": "Mill End",
         "distance": 105,
         "elevation": 803
         },
        {"group": "Doppio",
         "leader": "Andy Fry",
         "destination": "The Cow Shed",
         "distance": 110,
         "elevation": 750
         }]

    sunday_rides = [
        {"group": "Mixed",
         "leader": "Ian",
         "destination": "La Hogue",
         "distance": 89,
         "elevation": 551
         }]

    # ----------------------------------------------------------- #
    # Polylines for the GPX files
    # ----------------------------------------------------------- #
    saturday_gpxes = [ Gpx().one_gpx(1), Gpx().one_gpx(2), Gpx().one_gpx(3) ]
    saturday_polylines = create_polyline_set(saturday_gpxes)

    sunday_gpxes = [Gpx().one_gpx(12)]
    sunday_polylines = create_polyline_set(sunday_gpxes)


    # ----------------------------------------------------------- #
    # Dataset for the destination cafes
    # ----------------------------------------------------------- #

    cafes = [Cafe().one_cafe(5), Cafe().one_cafe(39), Cafe().one_cafe(8)]

    saturday_cafes = []
    for cafe in cafes:
        saturday_cafes.append({
            "position": {"lat": cafe.lat, "lng": cafe.lon},
            "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
            "color": OPEN_CAFE_COLOUR,
        })

    cafes = [Cafe().one_cafe(41)]

    sunday_cafes = []
    for cafe in cafes:
        sunday_cafes.append({
            "position": {"lat": cafe.lat, "lng": cafe.lon},
            "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
            "color": OPEN_CAFE_COLOUR,
        })



    # Render home page
    return render_template("weekend.html", year=current_year,
                           GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY, ELSR_HOME=ELSR_HOME, MAP_BOUNDS=MAP_BOUNDS,
                           saturday=saturday, saturday_rides=saturday_rides, saturday_cafes=saturday_cafes,
                           saturday_polylines=saturday_polylines,
                           sunday=sunday, sunday_rides=sunday_rides, sunday_cafes=sunday_cafes,
                           sunday_polylines=sunday_polylines)
