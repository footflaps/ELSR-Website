from flask import render_template, request, flash, abort, redirect, url_for, send_from_directory
from flask_login import login_required, current_user
from werkzeug import exceptions
import os
from datetime import date, datetime, timedelta
from threading import Thread
from ics import Calendar as icsCalendar, Event as icsEvent


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, update_last_seen, logout_barred_user, SUPER_ADMIN_USER_ID
from core.db_classifieds import Classified, CLASSIFIEDS_PHOTO_FOLDER




# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Show classifieds list
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/classifieds", methods=['GET'])
@update_last_seen
def classifieds():
    # ----------------------------------------------------------- #
    # Get all our classifieds
    # ----------------------------------------------------------- #
    classifieds = Classified().all()

    # ----------------------------------------------------------- #
    # Update image filenames with paths
    # ----------------------------------------------------------- #
    for classified in classifieds:
        classified.images = []
        for image_name in classified.image_filenames.split(','):
            print(f"image_name = '{image_name}'")
            filename = f"/img/classifieds_photos/{image_name}"
            # Check file(s) actually exist
            if os.path.exists(os.path.join(CLASSIFIEDS_PHOTO_FOLDER, os.path.basename(filename))):
                print(f"Found image '{image_name}'")
                classified.images.append(filename)


    return render_template("classifieds.html", year=current_year, classifieds=classifieds)


# -------------------------------------------------------------------------------------------------------------- #
# Add a buy advert
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/add_buy", methods=['GET'])
@update_last_seen
def add_buy():

    flash("Coming soon...")

    return render_template("classifieds.html", year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# Add a sell advert
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/add_sell", methods=['GET'])
@update_last_seen
def add_sell():

    flash("Coming soon...")

    return render_template("classifieds.html", year=current_year)