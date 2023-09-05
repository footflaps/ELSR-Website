from flask import render_template, request, flash, abort, send_from_directory
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFError
from wtforms import StringField, EmailField, SubmitField
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from threading import Thread
import os
import requests
from bs4 import BeautifulSoup


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, GPX_UPLOAD_FOLDER_ABS


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import OPEN_CAFE_COLOUR
from core.db_users import update_last_seen
from core.subs_graphjs import get_elevation_data
from core.subs_google_maps import polyline_json, google_maps_api_key, ELSR_HOME, MAP_BOUNDS, count_map_loads
from core.dB_events import Event
from core.subs_email_sms import contact_form_email


# -------------------------------------------------------------------------------------------------------------- #
# Import the other route pages
# -------------------------------------------------------------------------------------------------------------- #

# I don't know why these are needed here, but without it, it complains even though Pycharm highlights them
# saying they are not actually used!
from core.routes_users import login
from core.routes_cafes import cafe_list
from core.routes_gpx import gpx_list
from core.routes_admin import admin_page
from core.routes_messages import mark_read
from core.routes_events import delete_event
from core.routes_weekend import weekend
from core.routes_calendar import calendar


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

CHAINGANG_GPX_FILENAME = "gpx_el_cg_2023.gpx"

CHAINGANG_MEET_NEW =  [{
        "position": {"lat": 52.22528, "lng": 0.043116},
        "title": f'<a href="https://threehorseshoesmadingley.co.uk/">Three Horseshoes</a>',
        "color": OPEN_CAFE_COLOUR,
    }]

# Getting chaingang leaders
TARGET_URL = "https://www.strava.com/segments/31554922?filter=overall"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3"
}


# -------------------------------------------------------------------------------------------------------------- #
# Contact form
# -------------------------------------------------------------------------------------------------------------- #

class ContactForm(FlaskForm):
    name = StringField("Name", validators=[InputRequired("Please enter your name.")])
    email = EmailField("Email address", validators=[InputRequired("Please enter your email address.")])
    message = CKEditorField("Message", validators=[InputRequired("Please enter a message.")])
    submit = SubmitField("Send")


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def get_chaingang_top10():
    # Overall leader board
    response = requests.get(TARGET_URL, headers=headers)
    webpage = response.text
    soup = BeautifulSoup(webpage, "lxml")
    table = soup.find(id='segment-leaderboard')
    rows = []
    for i, row in enumerate(table.find_all('tr')):
        if i != 0:
            rows.append([el.text.strip() for el in row.find_all('td')])
    return rows


def user_ip():
    # Get user's IP
    if request.headers.getlist("X-Forwarded-For"):
        users_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        users_ip = request.remote_addr
    return users_ip


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# robots.txt and Apple icons
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/robots.txt')
@app.route('/apple-touch-icon')
@app.route('/apple-touch-icon-precomposed.png')
@app.route('/apple-touch-icon-120x120.png')
@app.route('/apple-touch-icon-120x120-precomposed.png')
def static_from_root():
    # ----------------------------------------------------------- #
    # Send link to download the file
    # ----------------------------------------------------------- #
    filename = request.path[1:]

    if "apple-touch" in request.path[1:]:
        return send_from_directory(directory="../core/static/img/", path="apple-touch-icon-120x120-precomposed.png")

    return send_from_directory(directory="../core/static/", path=filename)


# -------------------------------------------------------------------------------------------------------------- #
# Home
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/', methods=['GET'])
@update_last_seen
def home():
    # -------------------------------------------------------------------------------------------- #
    # Show Temporary Meeting Point
    # -------------------------------------------------------------------------------------------- #
    cafe_marker = [{
        "position": {"lat": ELSR_HOME["lat"], "lng": ELSR_HOME["lng"]},
        "title": f'Food vans by station',
        "color": OPEN_CAFE_COLOUR,
    }]

    # Map will launch centered here
    map_coords = {"lat": ELSR_HOME["lat"], "lng": ELSR_HOME["lng"]}

    # Increment map counts
    count_map_loads(1)

    flash("ELSR has a new Meeting Place!")

    # Render home page
    return render_template("main_home.html", year=current_year, cafes=cafe_marker, map_coords=map_coords,
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), ELSR_HOME=ELSR_HOME, MAP_BOUNDS=MAP_BOUNDS)


# -------------------------------------------------------------------------------------------------------------- #
# Chaingang
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/chaingang', methods=['GET'])
@update_last_seen
def chaingang():
    # -------------------------------------------------------------------------------------------- #
    # Show chaingang route
    # -------------------------------------------------------------------------------------------- #

    # ----------------------------------------------------------- #
    # Double check GPX file actually exists
    # ----------------------------------------------------------- #

    # This is  the absolute path to the file
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, CHAINGANG_GPX_FILENAME)

    # Check it exists before we try and parse it etc
    if not os.path.exists(filename):
        # Should never happen, but may as well handle it cleanly
        flash("Sorry, we seem to have lost that GPX file!")
        flash("Somebody should probably fire the web developer...")
        Event().log_event("One GPX Fail", f"Can't find '{filename}'!")
        app.logger.error(f"gpx_details(): Can't find '{filename}'!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Need path as weird Google proprietary JSON string thing
    # ----------------------------------------------------------- #
    polyline = polyline_json(filename)

    # ----------------------------------------------------------- #
    # Need cafe markers as weird Google proprietary JSON string
    # ----------------------------------------------------------- #
    cafe_markers = CHAINGANG_MEET_NEW

    # ----------------------------------------------------------- #
    # Get elevation data
    # ----------------------------------------------------------- #
    elevation_data = get_elevation_data(filename)

    # ----------------------------------------------------------- #
    # Leader boards from Strava
    # ----------------------------------------------------------- #
    leader_table = get_chaingang_top10()

    # Increment map counts
    count_map_loads(1)

    # Render home page
    return render_template("main_chaingang.html", year=current_year, leader_table=leader_table,
                           cafe_markers=cafe_markers, elevation_data=elevation_data,
                           polyline=polyline['polyline'], midlat=polyline['midlat'], midlon=polyline['midlon'],
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS)


# -------------------------------------------------------------------------------------------------------------- #
# TWR
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/twr', methods=['GET'])
@update_last_seen
def twr():
    # -------------------------------------------------------------------------------------------- #
    # Show The Bench
    # -------------------------------------------------------------------------------------------- #
    cafe_marker = [{
        "position": {"lat":  52.197020, "lng":  0.111206},
        "title": "The Bench",
        "color": OPEN_CAFE_COLOUR,
    }]

    # Increment map counts
    count_map_loads(1)

    # Render home page
    return render_template("main_twr.html", year=current_year, cafes=cafe_marker,
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS)


# -------------------------------------------------------------------------------------------------------------- #
# About
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/about", methods=['GET'])
@update_last_seen
def about():
    return render_template("main_about.html", year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# Contact
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/contact", methods=['GET', 'POST'])
@update_last_seen
def contact():
    # Need a form
    form = ContactForm()

    # Are we posting the completed form?
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        #   POST - form validated & submitted
        # ----------------------------------------------------------- #
        Thread(target=contact_form_email, args=(form.name.data, form.email.data, form.message.data,)).start()
        flash("Thankyou, your message has been sent!")

        # Clear the form
        form.email.data = ""
        form.name.data = ""
        form.message.data = ""

    elif request.method == 'POST':

        # ----------------------------------------------------------- #
        #   POST - form validation failed
        # ----------------------------------------------------------- #

        flash("Form not filled in properly, see below!")

    # ----------------------------------------------------------- #
    #   GET - Render page
    # ----------------------------------------------------------- #

    return render_template("main_contact.html", year=current_year, form=form)


# -------------------------------------------------------------------------------------------------------------- #
# How to plan a ride
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/plan", methods=['GET'])
@update_last_seen
def plan():
    return render_template("main_plan_a_ride.html", year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# How to download a GPX
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/gpx_guide", methods=['GET'])
@update_last_seen
def gpx_guide():
    return render_template("main_download_howto.html", year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# Uncut steerer tubes
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/uncut", methods=['GET'])
@update_last_seen
def uncut():
    return render_template("uncut_steerertubes.html", year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Error Handlers
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# ------------------------------------------------------------------------------------------------------------- #
# Generate a 500 error
# ------------------------------------------------------------------------------------------------------------- #

@app.route("/error", methods=['GET'])
def error():
    test = 1/0
    return render_template("uncut_steerertubes.html", year=current_year)


# ------------------------------------------------------------------------------------------------------------- #
# CSRF Error
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(CSRFError)
def csrf_error(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    flash("Detected a potential Cross Site Request Forgery (CSRF) with the form.")
    flash("NB Forms time out after 60 minutes.")
    app.logger.debug(f"400: CSRF Error '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}'.")
    Event().log_event("400", f"CSRF Error for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 400 status explicitly
    return render_template('400.html', year=current_year), 400


# ------------------------------------------------------------------------------------------------------------- #
# 400: Bad Request
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(400)
def bad_request(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"400: Bad request for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}'.")
    Event().log_event("400", f"Bad request for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 400 status explicitly
    return render_template('400.html', year=current_year), 400


# ------------------------------------------------------------------------------------------------------------- #
# 401: Unauthorized
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(401)
def unauthorized(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"401: Unauthorized for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}'.")
    Event().log_event("401", f"Unauthorized for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 401 status explicitly
    # NB Don't have a 401 page, just re-use 403
    return render_template('403.html', year=current_year), 401


# ------------------------------------------------------------------------------------------------------------- #
# 403: Forbidden
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(403)
def forbidden(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"403: Forbidden for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}'.")
    Event().log_event("403", f"Forbidden for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 403 status explicitly
    return render_template('403.html', year=current_year), 403


# ------------------------------------------------------------------------------------------------------------- #
# 404: Not Found
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(404)
def page_not_found(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"404: Not found for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}'.")
    Event().log_event("404", f"Not found for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 404 status explicitly
    return render_template('404.html', year=current_year), 404


# ------------------------------------------------------------------------------------------------------------- #
# 405: Method Not Allowed
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(405)
def method_not_allowed(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"405: Not allowed for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}'.")
    Event().log_event("405", f"Not allowed for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 405 status explicitly
    return render_template('403.html', year=current_year), 405


# ------------------------------------------------------------------------------------------------------------- #
# 413: Request Entity Too Large
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(413)
def file_too_large(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    flash("The file was too large, limit is 10 MB.")
    app.logger.debug(f"413: File too large for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}'.")
    Event().log_event("413", f"File too large for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 413 status explicitly
    return render_template('400.html', year=current_year), 413


# ------------------------------------------------------------------------------------------------------------- #
# 500: Internal server error
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(500)
def internal_server_error(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"500: Internal server error for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}'.")
    Event().log_event("500", f"Internal server error for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # now you're handling non-HTTP exceptions only
    return render_template("500.html", e=e), 500


# Have to register 500 with app to over rule the default built in 500 page
app.register_error_handler(500, internal_server_error)


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Main
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


if __name__ == "__main__":
    if os.path.exists("/home/ben_freeman_eu/elsr_website/ELSR-Website/env_vars.py"):
        app.run(debug=False)
    else:
        app.run(debug=False)

