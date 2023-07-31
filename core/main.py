from flask import render_template, url_for, request, flash, abort
from flask_login import current_user
from flask_googlemaps import Map
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, SubmitField
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from threading import Thread
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, dynamic_map_size, current_year, GPX_UPLOAD_FOLDER_ABS


# -------------------------------------------------------------------------------------------------------------- #
# Import our Cafe class for Home page
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe, ESPRESSO_LIBRARY_INDEX, OPEN_CAFE_ICON
from core.db_users import update_last_seen


# -------------------------------------------------------------------------------------------------------------- #
# Import the other pages
# -------------------------------------------------------------------------------------------------------------- #

# I don't know why these are needed here, but without it, it complains even though Pycharm highlights them
# saying they are not actually used!
from core.routes_users import login
from core.routes_cafes import cafe_list
from core.routes_gpx import gpx_list, markers_for_gpx, markers_for_cafes
from core.routes_admin import admin_page
from core.routes_messages import mark_read
from core.routes_events import delete_event
from core.send_emails import contact_form_email
from core.dB_events import Event

# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

CHAINGANG_GPX_FILENAME = "gpx_el_cg_2023.gpx"

CHAINGANG_MEET = [{
            'icon': OPEN_CAFE_ICON,
            'lat': 52.22528,
            'lng': 0.043116,
            'infobox': f'<a href="https://threehorseshoesmadingley.co.uk/">Three Horseshoes</a>'
    }]



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
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Home
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/', methods=['GET'])
@update_last_seen
def home():
    # -------------------------------------------------------------------------------------------- #
    # Show Espresso Library on a map
    # -------------------------------------------------------------------------------------------- #

    cafe = Cafe().one_cafe(ESPRESSO_LIBRARY_INDEX)

    # Create a list of markers
    cafe_marker = [{
            'icon': OPEN_CAFE_ICON,
            'lat': cafe.lat,
            'lng': cafe.lon,
            'infobox': f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>'
    }]

    cafemap = Map(
        identifier="cafemap",
        lat=cafe.lat,
        lng=cafe.lon,
        zoom=16,
        style=dynamic_map_size(),
        markers=cafe_marker
    )

    # Render home page
    return render_template("main_home.html", year=current_year, cafemap=cafemap)


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
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, CHAINGANG_GPX_FILENAME))

    # Check it exists before we try and parse it etc
    if not os.path.exists(filename):
        # Should never happen, but may as well handle it cleanly
        flash("Sorry, we seem to have lost that GPX file!")
        flash("Somebody should probably fire the web developer...")
        Event().log_event("One GPX Fail", f"Can't find '{filename}'!")
        app.logger.debug(f"gpx_details(): Can't find '{filename}'!")
        print(f"gpx_details(): Can't find '{filename}'!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Need a map of the route and nearby cafes
    # ----------------------------------------------------------- #
    markers = markers_for_gpx(filename)
    markers += CHAINGANG_MEET
    chaingang_map = Map(
        identifier="cafemap",
        lat=52.211001,
        lng=0.117207,
        fit_markers_to_bounds=True,
        style=dynamic_map_size(),
        markers=markers
    )

    # Render home page
    return render_template("main_chaingang.html", year=current_year, chaingang_map=chaingang_map)


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
        print("Sending email in a thread....")
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
    return render_template("how_to_plan_ride.html", year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# Uncut steerer tubes
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/uncut", methods=['GET'])
@update_last_seen
def uncut():
    return render_template("uncut_steerertubes.html", year=current_year)


# ------------------------------------------------------------------------------------------------------------- #
# Error Handlers
# ------------------------------------------------------------------------------------------------------------- #

@app.route("/error", methods=['GET'])
def error():
    test = 1/0
    return render_template("uncut_steerertubes.html", year=current_year)


@app.errorhandler(400)
def bad_request(e):
    # What page were they looking for?
    requested_route = request.path

    # Log error in event log
    app.logger.debug(f"400: Bad request for '{requested_route}', previous page was '{request.referrer}'.")
    Event().log_event("400", f"Bad request for '{requested_route}', previous page was '{request.referrer}'")

    # note that we set the 400 status explicitly
    return render_template('400.html', year=current_year), 400


@app.errorhandler(401)
def unauthorized(e):
    # What page were they looking for?
    requested_route = request.path

    # Log error in event log
    app.logger.debug(f"401: Unauthorized for '{requested_route}', previous page was '{request.referrer}'.")
    Event().log_event("401", f"Unauthorized for '{requested_route}', previous page was '{request.referrer}'")

    # note that we set the 401 status explicitly
    # NB Don't have a 401 page, just re-use 403
    return render_template('403.html', year=current_year), 401


@app.errorhandler(403)
def forbidden(e):
    # What page were they looking for?
    requested_route = request.path

    # Log error in event log
    app.logger.debug(f"403: Forbidden for '{requested_route}', previous page was '{request.referrer}'.")
    Event().log_event("403", f"Forbidden for '{requested_route}', previous page was '{request.referrer}'")

    # note that we set the 403 status explicitly
    return render_template('403.html', year=current_year), 403


@app.errorhandler(404)
def page_not_found(e):
    # What page were they looking for?
    requested_route = request.path

    # Log error in event log
    app.logger.debug(f"404: Not found for '{requested_route}', previous page was '{request.referrer}'.")
    Event().log_event("404", f"Not found for '{requested_route}', previous page was '{request.referrer}'")

    # note that we set the 404 status explicitly
    return render_template('404.html', year=current_year), 404

@app.errorhandler(413)
def file_too_large(e):
    # What page were they looking for?
    requested_route = request.path

    # Log error in event log
    flash("The file was too large, limit is 10 MB.")
    app.logger.debug(f"413: File too large for '{requested_route}', previous page was '{request.referrer}'.")
    Event().log_event("413", f"File too large for '{requested_route}', previous page was '{request.referrer}'")

    # note that we set the 413 status explicitly
    return render_template('400.html', year=current_year), 413


@app.errorhandler(500)
def internal_server_error(e):
    # What page were they looking for?
    requested_route = request.path

    # Log error in event log
    app.logger.debug(f"500: Internal server error for '{requested_route}', previous page was '{request.referrer}'.")
    Event().log_event("500", f"Internal server error for '{requested_route}', previous page was '{request.referrer}'")

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
        app.run(debug=True)

