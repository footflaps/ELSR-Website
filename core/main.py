from flask import render_template, request, flash, abort, send_from_directory, url_for, redirect
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, SubmitField
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from threading import Thread
import os
import requests as requests2
from bs4 import BeautifulSoup
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, GPX_UPLOAD_FOLDER_ABS, live_site, GLOBAL_FLASH

# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe, OPEN_CAFE_COLOUR, BEAN_THEORY_INDEX
from core.db_users import User, update_last_seen, ClothingSizesForm
from core.subs_graphjs import get_elevation_data
from core.subs_google_maps import polyline_json, google_maps_api_key, ELSR_HOME, MAP_BOUNDS, count_map_loads
from core.dB_events import Event
from core.subs_email_sms import contact_form_email

# -------------------------------------------------------------------------------------------------------------- #
# Import the other route pages
# -------------------------------------------------------------------------------------------------------------- #

# I don't know why these are needed here, but without it, it complains even though Pycharm highlights them
# saying they are not actually used!
from core.routes_users import user_page
from core.routes_cafes import cafe_list
from core.routes_gpx import gpx_list
from core.routes_gpx_edit import edit_route
from core.routes_admin import admin_page
from core.routes_messages import mark_read
from core.routes_events import delete_event
from core.routes_weekend import weekend
from core.routes_calendar import calendar
from core.routes_blog import blog
from core.routes_classifieds import classifieds
from core.routes_gravel import gravel
from core.routes_user_register import register
from core.routes_user_login_logout import login
from core.routes_admin_maps import enable_maps
from core.routes_polling import add_poll
from core.routes_polling_voting import swap_vote
from core.routes_socials import add_social
from core.routes_social_signup import social_cant
from core.routes_errors import csrf_error


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

CHAINGANG_GPX_FILENAME = "gpx_el_cg_2023.gpx"

CHAINGANG_MEET_NEW = [{
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
    response = requests2.get(TARGET_URL, headers=headers)
    webpage = response.text
    soup = BeautifulSoup(webpage, "lxml")
    table = soup.find(id='segment-leaderboard')
    rows = []
    for i, row in enumerate(table.find_all('tr')):
        if i != 0:
            rows.append([el.text.strip() for el in row.find_all('td')])
    return rows


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# robots.txt
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/robots.txt')
def static_from_root():
    # ----------------------------------------------------------- #
    # Send link to download the file
    # ----------------------------------------------------------- #
    filename = request.path[1:]

    return send_from_directory(directory="../core/static/", path=filename)


# -------------------------------------------------------------------------------------------------------------- #
# Front page
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/', methods=['GET'])
@update_last_seen
def welcome():
    # -------------------------------------------------------------------------------------------- #
    # Decide where to send them
    # -------------------------------------------------------------------------------------------- #

    if current_user.is_authenticated:
        # Logged in users see the blog
        return redirect(url_for('blog'))
    else:
        # New users see home
        return redirect(url_for('home'))


# -------------------------------------------------------------------------------------------------------------- #
# Home
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/home', methods=['GET'])
@update_last_seen
def home():
    # -------------------------------------------------------------------------------------------- #
    # Show Current Meeting Place
    # -------------------------------------------------------------------------------------------- #

    # Get the cafe
    cafe = Cafe().one_cafe(BEAN_THEORY_INDEX)

    # Create a GM marker
    cafe_marker = [{
        "position": {"lat": cafe.lat, "lng": cafe.lon},
        "title": f'<a href="{url_for("cafe_details", cafe_id=BEAN_THEORY_INDEX)}">{cafe.name}</a>',
        "color": OPEN_CAFE_COLOUR,
    }]

    # Increment map counts
    count_map_loads(1)

    # Temporary alert for change of meeting point
    if GLOBAL_FLASH:
        flash(GLOBAL_FLASH)

    # Render home page
    return render_template("main_home.html", year=current_year, cafes=cafe_marker, live_site=live_site(),
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
                           cafe_markers=cafe_markers, elevation_data=elevation_data, live_site=live_site(),
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
        "position": {"lat": 52.197020, "lng": 0.111206},
        "title": "The Bench",
        "color": OPEN_CAFE_COLOUR,
    }]

    # Increment map counts
    count_map_loads(1)

    # Render page
    return render_template("main_twr.html", year=current_year, cafes=cafe_marker, live_site=live_site(),
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS)


# -------------------------------------------------------------------------------------------------------------- #
# About
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/about", methods=['GET'])
@update_last_seen
def about():
    return render_template("main_about.html", year=current_year, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# GDPR
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/gdpr", methods=['GET'])
@update_last_seen
def gdpr():
    # ----------------------------------------------------------- #
    # List of all admins
    # ----------------------------------------------------------- #
    admins = User().all_admins()

    return render_template("main_gdpr.html", year=current_year, admins=admins, live_site=live_site())


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

    return render_template("main_contact.html", year=current_year, form=form, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# How to plan a ride
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/plan", methods=['GET'])
@update_last_seen
def plan():
    return render_template("main_plan_a_ride.html", year=current_year, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# How to download a GPX
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/gpx_guide", methods=['GET'])
@update_last_seen
def gpx_guide():
    return render_template("main_download_howto.html", year=current_year, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Uncut steerer tubes
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/uncut", methods=['GET'])
@update_last_seen
def uncut():
    return render_template("uncut_steerertubes.html", year=current_year, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Club kit page
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/club_kit", methods=['GET', 'POST'])
@app.route("/team_kit", methods=['GET', 'POST'])
@update_last_seen
def club_kit():
    # Need a form
    form = ClothingSizesForm()

    if current_user.is_authenticated:
        user = User().find_user_from_id(current_user.id)
        if not user:
            app.logger.debug(f"club_kit(): Failed to find user, if = '{current_user.id}'!")
            Event().log_event("club_kit Fail", f"Failed to find user, if = '{current_user.id}'!")
            abort(404)

        if request.method == 'GET':
            # ----------------------------------------------------------- #
            #   GET - Fill form in from dB
            # ----------------------------------------------------------- #

            # Populate form
            if user.clothing_size:
                sizes = json.loads(user.clothing_size)
                form.jersey_ss_relaxed.data = sizes['jersey_ss_relaxed']
                form.jersey_ss_race.data = sizes['jersey_ss_race']
                form.jersey_ls.data = sizes['jersey_ls']
                form.gilet.data = sizes['gilet']
                form.bib_shorts.data = sizes['bib_shorts']
                form.bib_longs.data = sizes['bib_longs']
                # Added this later, so won't always exist
                try:
                    form.notes.data = sizes['notes']
                except KeyError:
                    form.notes.data = ""

        # Are we posting the completed form?
        if form.validate_on_submit():

            # ----------------------------------------------------------- #
            #   POST - form validated & submitted
            # ----------------------------------------------------------- #
            sizes = {"jersey_ss_relaxed": form.jersey_ss_relaxed.data,
                     "jersey_ss_race": form.jersey_ss_race.data,
                     "jersey_ls": form.jersey_ls.data,
                     "gilet": form.gilet.data,
                     "bib_shorts": form.bib_shorts.data,
                     "bib_longs": form.bib_longs.data,
                     "notes": form.notes.data,
                     }
            user.clothing_size = json.dumps(sizes)
            user_id = user.id

            # Save to user
            if User().update_user(user):
                app.logger.debug(f"club_kit(): Updated user, user_id = '{user_id}'.")
                Event().log_event("club_kit Success", f"Updated user, user_id = '{user_id}'.")
                flash("Your sizes have been updated!")
            else:
                # Should never get here, but..
                app.logger.debug(f"club_kit(): Failed to update user, user_id = '{user_id}'.")
                Event().log_event("club_kit Fail", f"Failed to update user, user_id = '{user_id}'.")
                flash("Sorry, something went wrong!")

        elif request.method == 'POST':

            # ----------------------------------------------------------- #
            #   POST - form validation failed
            # ----------------------------------------------------------- #
            flash("Form not filled in properly, see below!")

    # ----------------------------------------------------------- #
    #   GET - Render page
    # ----------------------------------------------------------- #

    return render_template("main_club_kit.html", year=current_year, live_site=live_site(), form=form)


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
