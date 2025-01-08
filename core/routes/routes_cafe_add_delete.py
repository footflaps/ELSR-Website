from flask import render_template, redirect, url_for, flash, request, abort, Response
from flask_login import current_user
from werkzeug import exceptions
import mpu
import os
from threading import Thread


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site, delete_file_if_exists


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.user_repository import UserRepository
from core.database.repositories.cafe_repository import CafeRepository
from core.database.repositories.cafe_comment_repository import CafeCommentRepository
from core.database.repositories.event_repository import EventRepository

from core.decorators.user_decorators import update_last_seen, logout_barred_user, login_required, rw_required

from core.forms.cafe_forms import CreateCafeForm

from core.subs_gpx import check_new_cafe_with_all_gpxes, remove_cafe_from_all_gpxes
from core.subs_google_maps import ELSR_HOME, MAP_BOUNDS, google_maps_api_key, count_map_loads
from core.subs_cafe_photos import update_cafe_photo, CAFE_FOLDER


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
# Create new cafe
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/new_cafe", methods=["POST", "GET"])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def new_cafe() -> Response | str:
    # Need a form for the new cafe
    form = CreateCafeForm()

    # Prefill form
    if not form.detail.data:
        form.detail.data = "<ul>" \
                           "<li>Is the coffee good?  </li>" \
                           "<li>Does it do hot food? </li>" \
                           "<li>Do you need to book? </li>" \
                           "<li>Is there seating inside? </li>" \
                           "<li>Is there seating outside? </li>" \
                           "<li>Is it suitable for large groups eg 16 riders? </li>" \
                           "<li>Where does it rank on the ELSR Coke Price Index? ;-) </li>" \
                           "</ul>"

    # Are we posting the completed form?
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        #   POST - form submitted                                     #
        # ----------------------------------------------------------- #

        # Validate range
        range_km = mpu.haversine_distance((float(form.lat.data), float(form.lon.data)), (ELSR_LAT, ELSR_LON))
        if range_km > ELSR_MAX_KM:
            # Too far out of range from Cambridge
            app.logger.debug(f"new_cafe(): Fail, Lat and Lon are {round(range_km, 1)} km from Cambridge.")
            EventRepository().log_event("New Cafe Fail", f"Lat and Lon are {round(range_km, 1)} km from Cambridge.")
            flash(f"Lat and Lon are {round(range_km, 1)} km from Cambridge!")

            # Keep count of Google Map Loads
            count_map_loads(1)

            return render_template("cafe_add.html", form=form, cafe=None, year=current_year,
                                   GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS,
                                   ELSR_HOME=ELSR_HOME, live_site=live_site())

        # Create a new Cafe object
        cafe_name = form.name.data.strip()
        new_cafe = CafeRepository(
            name=cafe_name,
            lat=form.lat.data,
            lon=form.lon.data,
            website_url=form.website_url.data,
            details=form.detail.data,
            summary=form.summary.data,
            rating=form.rating.data,
            added_email=current_user.email
        )

        # ----------------------------------------------------------- #
        #   Name must be unique
        # ----------------------------------------------------------- #
        if CafeRepository().one_by_name(new_cafe.name):
            app.logger.debug(f"new_cafe(): Detected duplicate cafe name '{new_cafe.name}'.")
            EventRepository().log_event("New Cafe Fail", f"Detected duplicate cafe name '{new_cafe.name}'.")
            flash("Sorry, that name is already in use, choose another!")

            # Keep count of Google Map Loads
            count_map_loads(1)

            # Back to edit form
            return render_template("cafe_add.html", form=form, cafe=None, year=current_year,
                                   GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS,
                                   ELSR_HOME=ELSR_HOME, live_site=live_site())

        # ----------------------------------------------------------- #
        #   Try to add the cafe
        # ----------------------------------------------------------- #
        if CafeRepository().add_cafe(new_cafe):
            app.logger.debug(f"new_cafe(): Success, cafe '{cafe_name}' has been added!")
            EventRepository().log_event("New Cafe Success", f"Cafe '{cafe_name}' has been added!")
            flash(f"Cafe {cafe_name} has been added!")
        else:
            # Should never get here, but....
            app.logger.debug(f"new_cafe(): Cafe add failed '{cafe_name}'.")
            EventRepository().log_event("New Cafe Fail", f"Something went wrong! '{cafe_name}'.")
            flash("Sorry, something went wrong.")

            # Keep count of Google Map Loads
            count_map_loads(1)

            # Back to edit form
            return render_template("cafe_add.html", form=form, cafe=None, year=current_year,
                                   GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS,
                                   ELSR_HOME=ELSR_HOME, live_site=live_site())

        # ----------------------------------------------------------- #
        #   Look up our new cafe
        # ----------------------------------------------------------- #
        # Look up our new cafe in the dB as we can't know its ID until after it's been added
        cafe = CafeRepository().one_by_name(cafe_name)
        app.logger.debug(f"new_cafe(): Cafe added, cafe_id = '{cafe.id}'.")

        # ----------------------------------------------------------- #
        #   Did we get passed a path for a photo?
        # ----------------------------------------------------------- #
        if form.cafe_photo.data != "" and \
                form.cafe_photo.data is not None:
            # Upload the photo
            update_cafe_photo(form, cafe)

        # ----------------------------------------------------------- #
        #   Update GPX routes with new cafe etc
        # ----------------------------------------------------------- #

        app.logger.debug(f"new_cafe(): calling check_new_cafe_with_all_gpxes for '{cafe.name}'. ")
        flash(f"All GPX routes are being updated with distance to {cafe.name}.")
        # Update the routes in the background
        Thread(target=check_new_cafe_with_all_gpxes, args=(cafe,)).start()

        # Back to Cafe details page
        return redirect(url_for('cafe_details', cafe_id=cafe.id))  # type: ignore

    else:

        # ----------------------------------------------------------- #
        #   GET - Show blank edit form                                                                           #
        # ----------------------------------------------------------- #

        # Keep count of Google Map Loads
        count_map_loads(1)

        return render_template("cafe_add.html", form=form, cafe=None, year=current_year,
                               GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS,
                               ELSR_HOME=ELSR_HOME, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Edit a Cafe
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/edit_cafe", methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def edit_cafe() -> Response | str:
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    cafe_id = request.args.get('cafe_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not cafe_id:
        app.logger.debug(f"edit_cafe(): Missing cafe_id!")
        EventRepository().log_event("Edit Cafe Fail", f"Missing cafe_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = CafeRepository().one_by_id(cafe_id)

    # Check id is valid
    if not cafe:
        app.logger.debug(f"edit_cafe(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        EventRepository().log_event("Edit Cafe Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access to Admin or Author
    # ----------------------------------------------------------- #
    if not current_user.admin and \
            current_user.email != cafe.added_email:
        # Failed authentication
        app.logger.debug(f"edit_cafe(): Rejected request for '{current_user.email}' as no permissions for "
                         f"cafe_id = '{cafe_id}'.")
        EventRepository().log_event("Edit Cafe Fail", f"Rejected request for '{current_user.email}' as no permission for "
                                            f"cafe_id = '{cafe_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Need a form for the cafe details
    # ----------------------------------------------------------- #

    form = CreateCafeForm(
        name=cafe.name,
        lat=cafe.lat,
        lon=cafe.lon,
        website_url=cafe.website_url,
        summary=cafe.summary,
        rating=cafe.rating,
        detail=cafe.details
    )

    # Cache these so we can tell if the cafe coords have been updated
    last_lat = cafe.lat
    last_lon = cafe.lon

    # ----------------------------------------------------------- #
    # Handle POST request
    # ----------------------------------------------------------- #

    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        # Entry method #1 - form submitted successfully
        # ----------------------------------------------------------- #

        # Create a new BP object
        updated_cafe = CafeRepository(
            name=form.name.data,
            lat=form.lat.data,
            lon=form.lon.data,
            website_url=form.website_url.data,
            details=form.detail.data,
            summary=form.summary.data,
            rating=form.rating.data,
            added_email=current_user.email
        )

        # ----------------------------------------------------------- #
        #   Name must be unique
        # ----------------------------------------------------------- #
        if CafeRepository().one_by_name(updated_cafe.name) \
                and updated_cafe.name != cafe.name:
            # Duplicate cafe name, so tell then to stop copying....
            app.logger.debug(f"edit_cafe(): Detected duplicate cafe name '{updated_cafe.name}'.")
            EventRepository().log_event("Edit Cafe Fail", f"Detected duplicate cafe name '{updated_cafe.name}'.")
            flash("Sorry, that name is already in use, choose another!")

            # Keep count of Google Map Loads
            count_map_loads(1)

            # Back to edit form
            return render_template("cafe_add.html", cafe=cafe, form=form, year=current_year,
                                   GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS,
                                   ELSR_HOME=ELSR_HOME, live_site=live_site())

        # ----------------------------------------------------------- #
        # Update details
        # ----------------------------------------------------------- #
        if CafeRepository().update_cafe(cafe=updated_cafe):
            # Flash back a message
            app.logger.debug(f"edit_cafe(): Successfully updated the cafe, cafe_id = '{cafe_id}'.")
            EventRepository().log_event("Edit Cafe Success", f"Cafe updated '{updated_cafe.name}', cafe_id = '{cafe_id}'.")
            flash("The cafe details have been updated.")
        else:
            # Should never get here, but....
            app.logger.debug(f"edit_cafe(): Something went wrong with Cafe().update_cafe cafe_id = '{cafe_id}'.")
            EventRepository().log_event("Edit Cafe Fail", f"Something went wrong. cafe_id = '{cafe_id}'.")
            flash("Sorry, something went wrong!")

        # ----------------------------------------------------------- #
        #   Did we get passed a path for a photo?
        # ----------------------------------------------------------- #
        if form.cafe_photo.data != "" and \
                form.cafe_photo.data is not None:
            # Upload the photo
            update_cafe_photo(form, cafe)

        # ----------------------------------------------------------- #
        #   Update GPX routes with new cafe etc
        # ----------------------------------------------------------- #
        updated_cafe = CafeRepository().one_by_id(cafe_id)
        dist_km = mpu.haversine_distance((last_lat, last_lon), (updated_cafe.lat, updated_cafe.lon))

        # Only update GPX if it's really moved
        if dist_km >= ELSR_UPDATE_GPX_MIN_DISTANCE_KM:
            # Need to update all GPXes with new cafe location
            app.logger.debug(f"edit_cafe(): Cafe has moved {round(dist_km, 1)} km, so need to update GPXes.")
            flash(f"All GPX routes are being updated with distance to {updated_cafe.name}.")
            # Update the routes in the background, so page reloads quickly
            Thread(target=check_new_cafe_with_all_gpxes, args=(updated_cafe,)).start()
        else:
            # It's not moved enough to care
            app.logger.debug(f"edit_cafe(): Cafe has only moved {round(dist_km, 1)} km, so no need to update GPXes.")

        # Back to cafe details page
        return redirect(url_for('cafe_details', cafe_id=cafe_id))  # type: ignore

    # ----------------------------------------------------------- #
    # Handle GET
    # ----------------------------------------------------------- #

    # Flag as closed (if set)
    if not bool(cafe.active):
        flash("The cafe has been marked as closed / closing!")

    # Make sure cafe photo has correct path
    if cafe.image_name:
        cafe.image_name = f"/static/img/cafe_photos/{os.path.basename(cafe.image_name)}"

    # Keep count of Google Map Loads
    count_map_loads(1)

    # Show edit form for the specified cafe
    return render_template("cafe_add.html", cafe=cafe, form=form, year=current_year,
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), MAP_BOUNDS=MAP_BOUNDS,
                           ELSR_HOME=ELSR_HOME, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Delete a comment
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/delete_comment", methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def delete_comment() -> Response | str:
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    comment_id = request.args.get('comment_id', None)
    cafe_id = request.args.get('cafe_id', None)
    try:
        password = request.form['password']
    except exceptions.BadRequestKeyError:
        password = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if password == "":
        password = " "

    # ----------------------------------------------------------- #
    # Get user's IP
    # ----------------------------------------------------------- #
    if request.headers.getlist("X-Forwarded-For"):
        user_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        user_ip = request.remote_addr

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not comment_id:
        app.logger.debug(f"delete_comment(): Missing comment_id!")
        EventRepository().log_event("Delete Comment Fail", f"Missing comment_id!")
        return abort(400)
    elif not cafe_id:
        app.logger.debug(f"delete_comment(): Missing cafe_id!")
        EventRepository().log_event("Delete Comment Fail", f"Missing cafe_id!")
        return abort(400)
    elif not password:
        app.logger.debug(f"delete_comment(): Missing Password!")
        EventRepository().log_event("Delete Comment Fail", f"Missing Password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = CafeRepository().one_by_id(cafe_id)
    if not cafe:
        app.logger.debug(f"delete_comment(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        EventRepository().log_event("Delete Comment Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'.")
        return abort(404)

    comment = CafeCommentRepository().get_comment(comment_id)
    if not comment:
        app.logger.debug(f"delete_comment(): Failed to locate comment with comment_id = '{comment_id}'.")
        EventRepository().log_event("Delete Comment Fail", f"Failed to locate comment with comment_id = '{comment_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access to Admin or Author
    # ----------------------------------------------------------- #
    if not current_user.admin \
            and current_user.email != comment.email:
        # Failed authentication
        app.logger.debug(f"delete_comment(): Rejected request from '{current_user.email}' as no permissions"
                         f" for comment_id = '{comment_id}'.")
        EventRepository().log_event("Delete Comment Fail", f"Rejected request from user '{current_user.email}' as no "
                                                 f"permissions for comment_id = '{comment_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    #  Validate password
    # ----------------------------------------------------------- #
    # Need current user
    user = UserRepository().one_by_id(current_user.id)

    # Validate against current_user's password
    if not user.validate_password(user, password, user_ip):
        app.logger.debug(f"delete_comment(): Delete failed, incorrect password for user_id = '{user.id}'!")
        EventRepository().log_event("Delete Comment Fail", f"Incorrect password for user_id = '{user.id}'!")
        flash(f"Incorrect password for user {user.name}!")
        # Go back to route detail page
        return redirect(url_for('cafe_details', cafe_id=cafe_id))  # type: ignore

    # ----------------------------------------------------------- #
    # Delete comment
    # ----------------------------------------------------------- #
    if CafeCommentRepository().delete_comment(comment_id):
        # Success
        app.logger.debug(f"delete_comment(): Successfully deleted the comment, comment_id = '{comment_id}'.")
        EventRepository().log_event("Delete Comment Success", f"Successfully deleted the comment. comment_id = '{comment_id}''.")
        flash("Comment deleted.")
    else:
        # Should never get here, but....
        app.logger.debug(f"delete_comment(): Failed to delete the comment, comment_id = '{comment_id}'.")
        EventRepository().log_event("Delete Comment Fail", f"Failed to delete the comment, comment_id = '{comment_id}'.")
        flash("Sorry, something went wrong!")

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id, anchor="comments"))  # type: ignore


# -------------------------------------------------------------------------------------------------------------- #
# Delete cafe
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/delete_cafe", methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def delete_cafe() -> Response | str:
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    cafe_id = request.args.get('cafe_id', None)
    try:
        password = request.form['password']
    except exceptions.BadRequestKeyError:
        password = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if password == "":
        password = " "

    # ----------------------------------------------------------- #
    # Get user's IP
    # ----------------------------------------------------------- #
    if request.headers.getlist("X-Forwarded-For"):
        user_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        user_ip = request.remote_addr

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not cafe_id:
        app.logger.debug(f"delete_cafe(): Missing cafe_id!")
        EventRepository().log_event("Delete Cafe Fail", f"Missing cafe_id!")
        return abort(400)
    if not password:
        app.logger.debug(f"delete_cafe(): Missing password!")
        EventRepository().log_event("Delete Cafe Fail", f"Missing password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = CafeRepository().one_by_id(cafe_id)
    if not cafe:
        app.logger.debug(f"delete_cafe(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        EventRepository().log_event("Delete Cafe Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access to Admin or Author
    # ----------------------------------------------------------- #
    if not current_user.admin \
            and current_user.email != cafe.added_email:
        # Failed authentication
        app.logger.debug(f"delete_cafe(): Rejected request from '{current_user.email}' as no permissions"
                         f" for cafe_id = '{cafe_id}'.")
        EventRepository().log_event("Delete Cafe Fail", f"Rejected request from user '{current_user.email}' as no "
                                              f"permissions for cafe_id = '{cafe_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    #  Validate password
    # ----------------------------------------------------------- #
    # Need current user
    user = UserRepository().one_by_id(current_user.id)

    # Validate against current_user's password
    if not user.validate_password(user, password, user_ip):
        app.logger.debug(f"delete_cafe(): Delete failed, incorrect password for user_id = '{user.id}'!")
        EventRepository().log_event("Delete Cafe Fail", f"Incorrect password for user_id = '{user.id}'!")
        flash(f"Incorrect password for user {user.name}!")
        # Go back to socials page
        return redirect(url_for('cafe_details', cafe_id=cafe_id))  # type: ignore

    # ----------------------------------------------------------- #
    #  Delete any comments
    # ----------------------------------------------------------- #
    comments = CafeCommentRepository().all_comments_by_cafe_id(cafe.id)
    for comment in comments:
        if not CafeCommentRepository().delete_comment(comment.id):
            # This is not terminal, just leaves orphaned comments in the db
            app.logger.debug(f"delete_cafe(): Failed to delete cafe comment id = '{comment.id}'!")
            EventRepository().log_event("Delete Cafe Fail", f"Failed to delete cafe comment id = '{comment.id}'!")

    # ----------------------------------------------------------- #
    #  Delete any images
    # ----------------------------------------------------------- #
    if cafe.image_name:
        filename = os.path.join(CAFE_FOLDER, os.path.basename(cafe.image_name))
        delete_file_if_exists(filename)

    # ----------------------------------------------------------- #
    #  Remove cafe id from all GPX files
    # ----------------------------------------------------------- #
    app.logger.debug(f"delete_cafe(): calling remove_cafe_from_all_gpxes for cafe, id = '{cafe.id}'.")
    EventRepository().log_event("Delete Cafe Success", f"calling remove_cafe_from_all_gpxes for cafe, id = '{cafe.id}'.")
    # Update the routes in the background
    Thread(target=remove_cafe_from_all_gpxes, args=(cafe.id,)).start()

    # ----------------------------------------------------------- #
    #  Delete the cafe itself
    # ----------------------------------------------------------- #
    if CafeRepository().delete_cafe(cafe.id):
        # Success
        app.logger.debug(f"delete_cafe(): Successfully deleted the cafe, id = '{cafe.id}'.")
        EventRepository().log_event("Delete Cafe Success", f"Successfully deleted the cafe, id = '{cafe.id}'.")
        flash("Cafe deleted.")
    else:
        # Should never get here, but....
        app.logger.debug(f"delete_cafe(): Failed to delete the cafe, id = '{cafe.id}'.")
        EventRepository().log_event("Delete Cafe Fail", f"Failed to delete the cafe, id = '{cafe.id}'.")
        flash("Sorry, something went wrong!")

    # Back to cafe list page
    return redirect(url_for('cafe_list'))  # type: ignore

