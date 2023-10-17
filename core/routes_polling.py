from flask import render_template, url_for, request, flash, redirect, abort
from flask_login import login_required, current_user
from werkzeug import exceptions
from bbc_feeds import weather
from datetime import datetime, timedelta
import json
import os
from threading import Thread


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site



# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, update_last_seen, logout_barred_user
from core.dB_events import Event
from core.db_polls import Polls, CreatePollForm


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Weekend ride details
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/add_poll', methods=['GET', 'POST'])
@logout_barred_user
@update_last_seen
@login_required
def add_poll():
    # ----------------------------------------------------------- #
    # Did we get passed a poll id?
    # ----------------------------------------------------------- #
    poll_id = request.args.get('poll_id', None)

    # ----------------------------------------------------------- #
    # Get user
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(current_user.id)
    if not user:
        app.logger.debug(f"add_poll(): Failed to find user, if = '{current_user.id}'!")
        Event().log_event("add_poll Fail", f"Failed to find user, if = '{current_user.id}'!")
        abort(404)

    # ----------------------------------------------------------- #
    # Need a form
    # ----------------------------------------------------------- #
    form = CreatePollForm()


    # ----------------------------------------------------------- #
    #   GET - Render page
    # ----------------------------------------------------------- #

    return render_template("main_club_kit.html", year=current_year, live_site=live_site(), form=form)
