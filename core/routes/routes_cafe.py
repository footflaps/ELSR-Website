from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user
from datetime import date
from werkzeug import exceptions
import os
from threading import Thread
import time


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site, is_mobile, DOPPIO_GROUP, ESPRESSO_GROUP, DECAFF_GROUP, MIXED_GROUP


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.models.cafe_model import CafeModel
from core.database.repositories.user_repository import UserRepository
from core.database.repositories.cafe_repository import CafeRepository, OPEN_CAFE_COLOUR, CLOSED_CAFE_COLOUR
from core.database.repositories.cafe_comment_repository import CafeCommentRepository
from core.database.repositories.gpx_repository import GpxRepository
from core.database.repositories.message_repository import MessageModel, MessageRepository, ADMIN_EMAIL
from core.database.repositories.event_repository import EventRepository
from core.database.repositories.calendar_repository import CalendarRepository

from core.decorators.user_decorators import update_last_seen, logout_barred_user, login_required, rw_required

from core.forms.cafe_comment_forms import CreateCafeCommentForm

from core.subs_google_maps import create_polyline_set, MAX_NUM_GPX_PER_GRAPH, ELSR_HOME, MAP_BOUNDS, \
                                  google_maps_api_key, count_map_loads
from core.subs_email_sms import alert_admin_via_sms, send_message_notification_email


# -------------------------------------------------------------------------------------------------------------- #
# Constants used to verify sensible cafe coordinates
# -------------------------------------------------------------------------------------------------------------- #

# We only allow cafes within a sensible range to Cambridge
ELSR_LAT = 52.203316
ELSR_LON = 0.131689
ELSR_MAX_KM = 100

# Update routes for the cafe if it has moved by at least 100m
ELSR_UPDATE_GPX_MIN_DISTANCE_KM = 0.1


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Cafe list
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/cafes', methods=['GET'])
@update_last_seen
@logout_barred_user
def cafe_list():
    # ----------------------------------------------------------- #
    # Get all known cafes
    # ----------------------------------------------------------- #
    cafes = CafeRepository().all_cafes()

    # ----------------------------------------------------------- #
    # Map of all cafes
    # ----------------------------------------------------------- #

    # Create a list of markers
    cafe_markers = []

    for cafe in cafes:
        if cafe.active:
            colour = OPEN_CAFE_COLOUR
        else:
            colour = CLOSED_CAFE_COLOUR

        marker = {
            "position": {"lat": cafe.lat, "lng": cafe.lon},
            "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
            "color": colour,
        }
        cafe_markers.append(marker)

    # Map will launch centered here
    map_coords = {"lat": ELSR_LAT, "lng": ELSR_LON}

    # Keep count of Google Map Loads
    count_map_loads(1)

    # Render in main index template
    print("Serving page now...")
    return render_template("cafe_list.html", year=current_year, cafes=cafes, GOOGLE_MAPS_API_KEY=google_maps_api_key(),
                           cafe_markers=cafe_markers, map_coords=map_coords, ELSR_HOME=ELSR_HOME, MAP_BOUNDS=MAP_BOUNDS,
                           live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# List of top 10 most visited cafes
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/cafe_top10', methods=['GET'])
@update_last_seen
def cafe_top10():
    # ----------------------------------------------------------- #
    # Get all the rides
    # ----------------------------------------------------------- #
    rides = CalendarRepository().all_calendar()

    # This is our cafe list
    cafes = {}

    # Filter by Doppio, Espresso, Decaff and Mixed
    for ride in rides:
        if ride.group == DOPPIO_GROUP \
                or ride.group == ESPRESSO_GROUP \
                or ride.group == DECAFF_GROUP \
                or ride.group == MIXED_GROUP:
            # Grab the cafe ID (if set)
            cafe_id = ride.cafe_id
            if ride.cafe_id:
                if not cafe_id in cafes:
                    cafes[cafe_id] = 1
                else:
                    cafes[cafe_id] += 1
    # Sort dictionary
    sorted_cafes = dict(reversed(sorted(cafes.items(), key=lambda item: item[1])))

    # Build list for jinja
    cafes = []
    for index, data in sorted_cafes.items():
        cafe = CafeRepository().one_by_id(index)
        if cafe:
            cafes.append({"name": cafe.name,
                          "id": cafe.id,
                          "visits": data,
                          "routes": len(GpxRepository().find_all_gpx_for_cafe(cafe.id, current_user)),
                          "rating": cafe.rating,
                          })
        if len(cafes) >= 10:
            break

    # Render template
    return render_template("cafe_top10.html", year=current_year, mobile=is_mobile(), live_site=live_site(),
                           cafes=cafes)


# -------------------------------------------------------------------------------------------------------------- #
# View one cafe and be able to add a comment
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/cafe/<int:cafe_id>", methods=['GET', 'POST'])
@update_last_seen
@logout_barred_user
def cafe_details(cafe_id):
    anchor = request.args.get('anchor', None)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = CafeRepository().one_by_id(cafe_id)

    # Check id is valid
    if not cafe:
        app.logger.debug(f"cafe_details(): Failed to locate cafe with cafe.id = '{cafe_id}'.")
        EventRepository().log_event("Cafe Fail", f"Failed to locate cafe with cafe.id = '{cafe_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Prepare page contents
    # ----------------------------------------------------------- #

    # Need a comment form
    form = CreateCafeCommentForm()

    # Get any exiting comments for this cafe
    comments = CafeCommentRepository().all_comments_by_cafe_id(cafe_id)

    # Get all GPX routes which pass this cafe and that can be seen by current_user
    gpxes = GpxRepository().find_all_gpx_for_cafe(cafe_id, current_user)

    # -------------------------------------------------------------------------------------------- #
    # Map for where the cafe is
    # -------------------------------------------------------------------------------------------- #
    # Is cafe open or closed?
    if cafe.active:
        cafe_colour = OPEN_CAFE_COLOUR
    else:
        cafe_colour = CLOSED_CAFE_COLOUR

    # Need cafe markers as weird Google proprietary JSON string
    cafe_markers = [{
        "position": {"lat": cafe.lat, "lng": cafe.lon},
        "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
        "color": cafe_colour,
    }]

    # Map will launch centered here
    cafe_map_coords = {"lat": cafe.lat, "lng": cafe.lon}

    # ----------------------------------------------------------- #
    # Map for the possible routes
    # ----------------------------------------------------------- #
    polylines = create_polyline_set(gpxes)

    # Warn if we skipped any
    if len(gpxes) >= MAX_NUM_GPX_PER_GRAPH:
        warning = f"NB: Only showing first {MAX_NUM_GPX_PER_GRAPH} routes on map."
    else:
        warning = None

    # Are we posting the completed comment form?
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        # Handle POST
        # ----------------------------------------------------------- #

        # Who is trying to post
        user = UserRepository().find_user_from_id(current_user.id)
        if not user:
            # Should never get here, but....
            app.logger.debug(f"cafe_details(): Couldn't locate user, current_user.id = '{current_user.id}'.")
            EventRepository().log_event("Cafe Comment Fail", f"Couldn't locate user, current_user.id = '{current_user.id}'.")
            flash("Sorry, something went wrong.")
            return redirect(url_for('cafe_details', cafe_id=cafe.id))

        # ----------------------------------------------------------- #
        # Permission check for POST
        # ----------------------------------------------------------- #
        if not user.readwrite:
            # Should never get here, but....
            app.logger.debug(f"cafe_details(): User doesn't have write permissions user.id = '{user.id}'.")
            EventRepository().log_event("Cafe Comment Fail", f"User doesn't have write permissions user.id = '{user.id}'.")
            flash("Sorry, you do not have write permissions.")
            return redirect(url_for('cafe_details', cafe_id=cafe.id))

        # New comment
        new_comment = CafeCommentRepository(
            cafe_id=cafe.id,
            date=date.today().strftime("%B %d, %Y"),
            email=current_user.email,
            name=current_user.name,
            body=form.body.data
        )

        # Add to the dB
        if CafeCommentRepository().add_comment(new_comment):
            # Success!
            app.logger.debug(f"cafe_details(): Comment posted successfully cafe.id = '{cafe.id}'.")
            EventRepository().log_event("Cafe Comment Success", f"Comment posted successfully cafe.id = '{cafe.id}'.")
        else:
            # Should never get here, but....
            app.logger.debug(f"cafe_details(): Comment post failed cafe.id = '{cafe.id}'.")
            EventRepository().log_event("Cafe Comment Fail", f"Comment post failed.")

        # We can't reset form, so to show the post completed, we have to redirect
        # back to the start of ourselves.
        return redirect(url_for('cafe_details', cafe_id=cafe.id))

    elif request.method == 'POST':

        # This traps a post, but where the form verification failed.
        flash("Comment failed to post - did you write anything?")

        # Flag as closed
        if not bool(cafe.active):
            flash("The cafe has been marked as closed / closing!")

        # Make sure cafe photo has correct path for displaying in html
        if cafe.image_name:
            cafe.image_name = f"/static/img/cafe_photos/{os.path.basename(cafe.image_name)}"

        # Keep count of Google Map Loads
        count_map_loads(1)

        # Render using cafe details template
        return render_template("cafe_details.html", cafe=cafe, form=form, comments=comments, year=current_year,
                               gpxes=gpxes, cafes=cafe_markers, cafe_map_coords=cafe_map_coords,
                               GOOGLE_MAPS_API_KEY=google_maps_api_key(), polylines=polylines, warning=warning,
                               MAP_BOUNDS=MAP_BOUNDS, live_site=live_site(), anchor="comments")

    else:

        # ----------------------------------------------------------- #
        # Handle GET
        # ----------------------------------------------------------- #

        # Flag as closed
        if not bool(cafe.active):
            flash("The cafe has been marked as closed / closing!")

        # Make sure cafe photo has correct path
        if cafe.image_name:
            cafe.image_name = f"/static/img/cafe_photos/{os.path.basename(cafe.image_name)}"

        # Keep count of Google Map Loads
        count_map_loads(1)

        # Render using cafe details template
        return render_template("cafe_details.html", cafe=cafe, form=form, comments=comments, year=current_year,
                               gpxes=gpxes, cafes=cafe_markers, cafe_map_coords=cafe_map_coords,
                               GOOGLE_MAPS_API_KEY=google_maps_api_key(), warning=warning,
                               polylines=polylines['polylines'], midlat=polylines['midlat'], midlon=polylines['midlon'],
                               MAP_BOUNDS=MAP_BOUNDS, live_site=live_site(), anchor=anchor)


# -------------------------------------------------------------------------------------------------------------- #
# Mark a cafe as being closed
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/close_cafe>", methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def close_cafe():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    cafe_id = request.args.get('cafe_id', None)
    try:
        details = request.form['details']
    except exceptions.BadRequestKeyError:
        details = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not cafe_id:
        app.logger.debug(f"close_cafe(): Missing cafe_id!")
        EventRepository().log_event("Close Cafe Fail", f"Missing cafe_id")
        return abort(400)
    elif not details:
        app.logger.debug(f"close_cafe(): Missing details!")
        EventRepository().log_event("Close Cafe Fail", f"Missing details")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = CafeRepository().one_by_id(cafe_id)
    if not cafe:
        app.logger.debug(f"close_cafe(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        EventRepository().log_event("Close Cafe Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access to Admin or Author
    # ----------------------------------------------------------- #
    if not current_user.admin and \
            current_user.email != cafe.added_email:
        # Failed authentication
        app.logger.debug(f"close_cafe(): Rejected request from '{current_user.email}' as no permissions"
                         f" for cafe.id = '{cafe.id}'.")
        EventRepository().log_event("Close Cafe Fail", f"Rejected request from '{current_user.email}' as no permissions"
                                             f" for cafe.id = '{cafe.id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Close the cafe
    # ----------------------------------------------------------- #
    if CafeRepository().close_cafe(cafe.id, details):
        # Success
        app.logger.debug(f"close_cafe(): Successfully closed the cafe, cafe.id = '{cafe.id}'.")
        EventRepository().log_event("Close Cafe Success", f"Cafe marked as closed. cafe.id = '{cafe.id}'.")
        flash("Cafe marked as closed.")
    else:
        # Should never get here, but....
        app.logger.debug(f"close_cafe(): Cafe().close_cafe() failed with cafe.id = '{cafe.id}'.")
        EventRepository().log_event("Close Cafe Fail", f"Cafe().close_cafe() failed with cafe.id = '{cafe.id}'.")
        flash("Sorry, something went wrong!")

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id))


# -------------------------------------------------------------------------------------------------------------- #
# Mark a cafe as not being closed
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/unclose_cafe", methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def unclose_cafe():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    cafe_id = request.args.get('cafe_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not cafe_id:
        app.logger.debug(f"unclose_cafe(): Missing cafe_id!")
        EventRepository().log_event("unClose Cafe Fail", f"Missing cafe_id")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = CafeRepository().one_by_id(cafe_id)

    if not cafe:
        app.logger.debug(f"unclose_cafe(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        EventRepository().log_event("unClose Cafe Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access to Admin or Author
    # ----------------------------------------------------------- #
    if not current_user.admin \
            and current_user.email != cafe.added_email:
        # Failed authentication
        app.logger.debug(f"unclose_cafe(): Rejected request from '{current_user.email}' as no permissions"
                         f" for cafe.id = '{cafe.id}'.")
        EventRepository().log_event("unClose Cafe Fail", f"Rejected request as no permissions. cafe_id = '{cafe_id}'")
        return abort(403)

    # ----------------------------------------------------------- #
    # Open the cafe
    # ----------------------------------------------------------- #
    if CafeRepository().unclose_cafe(cafe.id):
        # Success!
        app.logger.debug(f"unclose_cafe(): Successfully unclosed cafe with cafe_id = '{cafe_id}'.")
        EventRepository().log_event("unClose Cafe Success", f"Successfully unclosed the cafe. cafe_id = '{cafe_id}'")
        flash("Cafe marked as open.")
    else:
        # Should never get here, but....
        app.logger.debug(f"unclose_cafe(): Cafe().unclose_cafe() failed with cafe_id = '{cafe_id}'.")
        EventRepository().log_event("unClose Cafe Fail", f"Something went wrong. cafe_id = '{cafe_id}'")
        flash("Sorry, something went wrong!")

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id))


# -------------------------------------------------------------------------------------------------------------- #
# Flag a cafe to an admin
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/flag_cafe", methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def flag_cafe():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    cafe_id = request.args.get('cafe_id', None)

    if cafe_id:
        try:
            int(cafe_id)
        except ValueError:
            flash(f"Invalid cafe id '{cafe_id}'!")
            return abort(404)

    try:
        reason = request.form['reason']
    except exceptions.BadRequestKeyError:
        reason = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if reason == "":
        reason = " "

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not reason:
        app.logger.debug(f"flag_cafe(): Missing reason!")
        EventRepository().log_event("Flag Cafe Fail", f"Missing reason!")
        return abort(400)
    elif not cafe_id:
        app.logger.debug(f"flag_cafe(): Missing cafe_id!")
        EventRepository().log_event("Flag Cafe Fail", f"Missing cafe_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe: CafeModel | None = CafeRepository().one_by_id(int(cafe_id))
    if not cafe:
        app.logger.debug(f"flag_cafe(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        EventRepository().log_event("Flag Cafe Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'")
        return abort(404)

    # ----------------------------------------------------------- #
    # Send a message to Admin
    # ----------------------------------------------------------- #
    message: MessageModel = MessageModel(
        from_email=current_user.email,
        to_email=ADMIN_EMAIL,
        body=f"Cafe Objection to '{cafe.name}' (id={cafe.id}). Reason: {reason}"
    )
    # Send it
    message = MessageRepository().add_message(message)
    # Either get back the message or None
    if message:
        # Success
        Thread(target=send_message_notification_email, args=(message, ADMIN_EMAIL,)).start()
        app.logger.debug(f"flag_cafe(): Flagged cafe, cafe_id = '{cafe_id}'.")
        EventRepository().log_event("Flag Cafe Success", f"Flagged cafe, cafe_id = '{cafe_id}', reason = '{reason}'.")
        flash("Your message has been forwarded to an admin.")
    else:
        # Should never get here, but....
        app.logger.debug(f"flag_cafe(): Message().add_message failed, cafe_id = '{cafe_id}'.")
        EventRepository().log_event("Flag Cafe Fail",
                          f"Message().add_message failed, cafe_id = '{cafe_id}', reason = '{reason}'.")
        flash("Sorry, something went wrong.")

    # ----------------------------------------------------------- #
    # Alert admin via SMS
    # ----------------------------------------------------------- #
    # Threading won't have access to current_user, so need to acquire persistent user to pass on
    user = UserRepository().find_user_from_id(current_user.id)
    Thread(target=alert_admin_via_sms, args=(user, f"Cafe '{cafe.name}', Reason: '{reason}'",)).start()

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id))


