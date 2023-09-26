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
from core.db_blog import Blog, create_blogs_form, STICKY, NON_STICKY, PRIVATE_NEWS, BLOG_PHOTO_FOLDER, NO_CAFE, \
                         NO_GPX, DRUNK_OPTION, CCC_OPTION, EVENT_OPTION
from core.dB_events import Event
from core.dB_cafes import Cafe
from core.dB_gpx import Gpx
from core.subs_blog_photos import update_blog_photo, delete_blog_photos
from core.subs_email_sms import alert_admin_via_sms, send_blog_notification_emails
from core.routes_calendar import ICS_DIRECTORY



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

    return render_template("classifieds.html", year=current_year)


@app.route("/add_buy", methods=['GET'])
@update_last_seen
def add_buy():

    flash("Coming soon...")

    return render_template("classifieds.html", year=current_year)


@app.route("/add_sell", methods=['GET'])
@update_last_seen
def add_sell():

    flash("Coming soon...")

    return render_template("classifieds.html", year=current_year)