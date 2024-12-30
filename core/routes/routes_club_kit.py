from flask import render_template, request, flash, abort
from flask_login import current_user
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.user_repository import UserRepository
from core.database.repositories.event_repository import EventRepository
from core.decorators.user_decorators import update_last_seen
from core.forms.user_forms import ClothingSizesForm


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/club_kit", methods=['GET', 'POST'])
@app.route("/team_kit", methods=['GET', 'POST'])
@update_last_seen
def club_kit():
    # Need a form
    form = ClothingSizesForm()

    if current_user.is_authenticated:
        user = UserRepository().find_user_from_id(current_user.id)
        if not user:
            app.logger.debug(f"club_kit(): Failed to find user, if = '{current_user.id}'!")
            EventRepository().log_event("club_kit Fail", f"Failed to find user, if = '{current_user.id}'!")
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
            if UserRepository().update_user(user):
                app.logger.debug(f"club_kit(): Updated user, user_id = '{user_id}'.")
                EventRepository().log_event("club_kit Success", f"Updated user, user_id = '{user_id}'.")
                flash("Your sizes have been updated!")
            else:
                # Should never get here, but..
                app.logger.debug(f"club_kit(): Failed to update user, user_id = '{user_id}'.")
                EventRepository().log_event("club_kit Fail", f"Failed to update user, user_id = '{user_id}'.")
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
# Legacy (2023) Club kit page
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/club_kit_v1", methods=['GET', 'POST'])
@app.route("/team_kit_v1", methods=['GET', 'POST'])
@update_last_seen
def club_kit_v1():

    # ----------------------------------------------------------- #
    #   Render page
    # ----------------------------------------------------------- #

    return render_template("main_club_kit_v1.html", year=current_year, live_site=live_site())
