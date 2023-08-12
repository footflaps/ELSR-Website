from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import date
from flask_googlemaps import Map
from werkzeug import exceptions
import gpxpy
import gpxpy.gpx
import mpu
import os
from threading import Thread
from PIL import Image


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS, dynamic_map_size, current_year, delete_file_if_exists, is_mobile

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe, CreateCafeForm, OPEN_CAFE_ICON, CLOSED_CAFE_ICON
from core.dB_cafe_comments import CafeComment, CreateCafeCommentForm
from core.routes_gpx import check_new_cafe_with_all_gpxes
from core.dB_gpx import Gpx
from core.routes_gpx import MIN_DISPLAY_STEP_KM
from core.db_messages import Message, ADMIN_EMAIL
from core.dB_events import Event
from core.db_users import User, update_last_seen, logout_barred_user
from core.send_emails import alert_admin_via_sms


# -------------------------------------------------------------------------------------------------------------- #
# Import our modal forms
# -------------------------------------------------------------------------------------------------------------- #

# These are needed, used in html templates, but PyCharm can't see that
from core.modal_forms import delete_comment_modal_form, delete_post_modal_form

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
# Constants used for uploading pictures of the cafes
# -------------------------------------------------------------------------------------------------------------- #

IMAGE_ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
CAFE_FOLDER = os.environ['ELSR_CAFE_FOLDER']
TARGET_PHOTO_SIZE = 150000


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in IMAGE_ALLOWED_EXTENSIONS


def map_icon(route_num):
    while route_num > 36:
        route_num -= 36
    if route_num <= 10:
        return f"https://maps.google.com/mapfiles/kml/paddle/{route_num}-lv.png"
    else:
        letter = chr(97 + route_num - 11)
        return f"https://maps.google.com/mapfiles/kml/paddle{letter}-lv.png"


def new_cafe_photo_filename(cafe):
    if not cafe.image_name:
        # First photo for this cafe
        return f"cafe_{cafe.id}.jpg"
    elif not os.path.exists(os.path.join(CAFE_FOLDER, os.path.basename(cafe.image_name))):
        # The current referenced photo isn't there, so just reset
        return f"cafe_{cafe.id}.jpg"
    else:
        # Already have a photo in use
        current_name = os.path.basename(cafe.image_name)
        # If we use the same filename the browser won't realise it's changed and just uses the cached one, so we
        # have to create a new filename.
        if current_name == f"cafe_{cafe.id}.jpg":
            # This will be the first new photo, so start at index 1
            return f"cafe_{cafe.id}_1.jpg"
        else:
            # Already using indices, so need to increment by one
            try:
                # Split[2] might fail if there aren't enough '_' in the filename
                index = current_name.split('_')[2].split('.')[0]
                index = int(index) + 1
                return f"cafe_{cafe.id}_{index}.jpg"
            except IndexError:
                # Just reset to 1
                return f"cafe_{cafe.id}_1.jpg"


def shrink_image(filename):
    # Get the image size for the os
    image_size = os.path.getsize(filename)

    # Quit now if the file is already a sensible size
    if image_size <= TARGET_PHOTO_SIZE:
        app.logger.debug(f"shrink_image(): Photo '{os.path.basename(filename)}' is small enough already.")

    else:
        app.logger.debug(f"shrink_image(): Photo '{os.path.basename(filename)}' will be shrunk!")

        # Shrinkage factor (trial and error led to the method)
        scaler = (TARGET_PHOTO_SIZE / image_size)**0.45

        # Open and shrink teh image
        img = Image.open(filename)
        img = img.resize((int(img.size[0] * scaler), int(img.size[1] * scaler)))

        # Save as same file
        img.save(filename, optimize=True)


def update_cafe_photo(form, cafe):
    app.logger.debug(f"update_cafe_photo(): Passed photo '{form.cafe_photo.data.filename}'")

    if allowed_file(form.cafe_photo.data.filename):
        # Create a new filename for the image
        filename = os.path.join(CAFE_FOLDER, new_cafe_photo_filename(cafe))
        app.logger.debug(f"update_cafe_photo(): New filename for photo = '{filename}'")

        # Make sure it's not there already
        if delete_file_if_exists(filename):

            # Upload and save in our cafe photo folder
            form.cafe_photo.data.save(filename)

            # Update cafe object with filename
            if Cafe().update_photo(cafe.id, f"{os.path.basename(filename)}"):
                # Uploaded OK
                app.logger.debug(f"update_cafe_photo(): Successfully uploaded the photo.")
                Event().log_event("Cafe Pass", f"Cafe photo updated. cafe.id = '{cafe.id}'.")
                flash("Cafe photo has been uploaded.")
            else:
                # Failed to upload eg invalid path
                app.logger.debug(f"update_cafe_photo(): Failed to upload the photo '{filename}' for cafe '{cafe.id}'.")
                Event().log_event("Add Cafe Fail", f"Couldn't upload file '{filename}' for cafe '{cafe.id}'.")
                flash(f"Sorry, failed to upload the file '{filename}!")

            # Shrink image if too large
            shrink_image(os.path.join(CAFE_FOLDER, filename))

        else:
            # Failed to delete existing file
            # NB delete_file_if_exists() will generate an error with details etc, so just flash here
            flash("Sorry, something went wrong!")

    else:
        # allowed_file() failed.
        app.logger.debug(f"update_cafe_photo(): Invalid file type for image.")
        Event().log_event("Cafe Fail", f"Invalid image filename '{os.path.basename(form.cafe_photo.data.filename)}',"
                                       f"permitted file types are '{IMAGE_ALLOWED_EXTENSIONS}'.")
        flash("Invalid file type for image!")


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
def cafe_list():
    # ----------------------------------------------------------- #
    # Get all known cafes
    # ----------------------------------------------------------- #

    cafes = Cafe().all_cafes()

    # ----------------------------------------------------------- #
    # Map of all cafes
    # ----------------------------------------------------------- #

    # Create a list of markers
    cafe_markers = []

    for cafe in cafes:
        if cafe.active:
            icon = OPEN_CAFE_ICON
        else:
            icon = CLOSED_CAFE_ICON

        marker = {
            'icon': icon,
            'lat': cafe.lat,
            'lng': cafe.lon,
            'infobox': f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>'
        }
        cafe_markers.append(marker)

    cafemap = Map(
        identifier="cafemap",
        lat=52.211001,
        lng=0.117207,
        fit_markers_to_bounds=True,
        style=dynamic_map_size(),
        markers=cafe_markers
    )

    # Render in main index template
    return render_template("cafe_list.html", year=current_year, cafes=cafes, cafemap=cafemap, mobile=is_mobile())


# -------------------------------------------------------------------------------------------------------------- #
# View one cafe and be able to add a comment
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/cafe/<int:cafe_id>", methods=['GET', 'POST'])
@update_last_seen
def cafe_details(cafe_id):
    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = Cafe().one_cafe(cafe_id)

    # Check id is valid
    if not cafe:
        app.logger.debug(f"cafe_details(): Failed to locate cafe with cafe.id = '{cafe_id}'.")
        Event().log_event("Cafe Fail", f"Failed to locate cafe with cafe.id = '{cafe_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Prepare page contents
    # ----------------------------------------------------------- #

    # Need a comment form
    form = CreateCafeCommentForm()

    # Get any exiting comments for this cafe
    comments = CafeComment().all_comments_by_id(cafe_id)

    # Get all GPX routes which pass this cafe and that can be seen by current_user
    gpxes = Gpx().find_all_gpx_for_cafe(cafe_id, current_user)

    # ----------------------------------------------------------- #
    # Map for where the cafe is
    # ----------------------------------------------------------- #

    cafe_marker = []
    cafe_marker.append({
        'icon': 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png',
        'lat': cafe.lat,
        'lng': cafe.lon,
        'infobox': cafe.name
    })

    # Create a Google Map for this cafe
    cafemap = Map(
        identifier="cafemap",
        lat=cafe.lat,
        lng=cafe.lon,
        zoom=14,
        style=dynamic_map_size(),
        markers=cafe_marker
    )

    # ----------------------------------------------------------- #
    # Map for the possible routes
    # ----------------------------------------------------------- #

    # Create a list of markers
    gpx_markers = cafe_marker
    track_num = 0

    for gpx in gpxes:

        # Need absolute path
        abs_filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))

        # Add the GPX route to markers
        gpx_file = open(abs_filename, 'r')
        gpx_track = gpxpy.parse(gpx_file)
        track_num += 1

        for track in gpx_track.tracks:
            for segment in track.segments:

                # Need these for working out inter sample spacing
                last_lat = segment.points[0].latitude
                last_lon = segment.points[0].longitude

                for point in segment.points:

                    # We sub-sample the raw GPX file as if you plot all the points, the map looks a complete mess.
                    # 0.5km spacing seems to work ok.
                    if mpu.haversine_distance((last_lat, last_lon),
                                              (point.latitude, point.longitude)) > MIN_DISPLAY_STEP_KM * 2:
                        gpx_markers.append({
                            'icon': map_icon(track_num),
                            'lat': point.latitude,
                            'lng': point.longitude,
                            'infobox': f'<a href="{url_for("gpx_details", gpx_id=gpx.id)}">Route: "{gpx.name}"</a>'
                        })

                        last_lat = point.latitude
                        last_lon = point.longitude

    # Create the Google Map config
    gpxmap = Map(
        identifier="gpxmap",
        lat=52.211001,
        lng=0.117207,
        fit_markers_to_bounds=True,
        style=dynamic_map_size(),
        markers=gpx_markers
    )

    # Are we posting the completed comment form?
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        # Handle POST
        # ----------------------------------------------------------- #

        # New comment
        new_comment = CafeComment(
            article_id=cafe.id,
            date=date.today().strftime("%B %d, %Y"),
            email=current_user.email,
            name=current_user.name,
            body=form.body.data
        )

        # Add to the dB
        if CafeComment().add_comment(new_comment):
            # Success!
            app.logger.debug(f"cafe_details(): Comment posted successfully cafe.id = '{cafe.id}'.")
            Event().log_event("Cafe Comment Success", f"Comment posted successfully cafe.id = '{cafe.id}'.")
        else:
            # Should never get here, but....
            app.logger.debug(f"cafe_details(): Comment post failed cafe.id = '{cafe.id}'.")
            Event().log_event("Cafe Comment Fail", f"Comment post failed.")

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
            app.logger.debug(f"cafe_detail(): cafe.image_name = '{cafe.image_name}'")

        # Render using cafe details template
        return render_template("cafe_details.html", cafe=cafe, form=form, comments=comments, year=current_year,
                               cafemap=cafemap, gpxes=gpxes, gpxmap=gpxmap, mobile=is_mobile())

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
            app.logger.debug(f"cafe_detail(): cafe.image_name = '{cafe.image_name}'")

        # Render using cafe details template
        return render_template("cafe_details.html", cafe=cafe, form=form, comments=comments, year=current_year,
                               cafemap=cafemap, gpxes=gpxes, gpxmap=gpxmap, mobile=is_mobile())


# -------------------------------------------------------------------------------------------------------------- #
# Create new cafe
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/new_cafe", methods=["POST", "GET"])
@logout_barred_user
@login_required
@update_last_seen
def new_cafe():
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
            Event().log_event("New Cafe Fail", f"Lat and Lon are {round(range_km, 1)} km from Cambridge.")
            flash(f"Lat and Lon are {round(range_km, 1)} km from Cambridge!")
            return render_template("cafe_add.html", form=form, cafe=None, year=current_year)

        # Create a new Cafe object
        new_cafe = Cafe(
            name=form.name.data.strip(),
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
        if Cafe().find_by_name(new_cafe.name):
            app.logger.debug(f"new_cafe(): Detected duplicate cafe name '{new_cafe.name}'.")
            Event().log_event("New Cafe Fail", f"Detected duplicate cafe name '{new_cafe.name}'.")
            flash("Sorry, that name is already in use, choose another!")
            # Back to edit form
            return render_template("cafe_add.html", form=form, cafe=None, year=current_year)

        # ----------------------------------------------------------- #
        #   Try to add the cafe
        # ----------------------------------------------------------- #
        if Cafe().add_cafe(new_cafe):
            app.logger.debug(f"new_cafe(): Success, cafe '{new_cafe.name}' has been added!")
            Event().log_event("New Cafe Success", f"Cafe '{new_cafe.name}' has been added!")
            flash(f"Cafe {new_cafe.name} has been added!")
        else:
            # Should never get here, but....
            app.logger.debug(f"new_cafe(): Cafe add failed '{new_cafe.name}'.")
            Event().log_event("New Cafe Fail", f"Something went wrong! '{new_cafe.name}'.")
            flash("Sorry, something went wrong.")
            # Back to edit form
            return render_template("cafe_add.html", form=form, cafe=None, year=current_year)

        # ----------------------------------------------------------- #
        #   Look up our new cafe
        # ----------------------------------------------------------- #
        # Look up our new cafe in the dB as we can't know its ID until after it's been added
        cafe = Cafe().find_by_name(new_cafe.name)
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
        return redirect(url_for('cafe_details', cafe_id=cafe.id))

    else:

        # ----------------------------------------------------------- #
        #   GET - Show blank edit form                                                                           #
        # ----------------------------------------------------------- #

        return render_template("cafe_add.html", form=form, cafe=None, year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# Edit a Cafe
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/edit_cafe", methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def edit_cafe():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    cafe_id = request.args.get('cafe_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not cafe_id:
        app.logger.debug(f"edit_cafe(): Missing cafe_id!")
        Event().log_event("Edit Cafe Fail", f"Missing cafe_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = Cafe().one_cafe(cafe_id)

    # Check id is valid
    if not cafe:
        app.logger.debug(f"edit_cafe(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        Event().log_event("Edit Cafe Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if not current_user.admin() \
            and current_user.email != cafe.added_email:
        # Failed authentication
        app.logger.debug(f"edit_cafe(): Rejected request for '{current_user.email}' as no permissions.")
        Event().log_event("Edit Cafe Fail", f"Rejected request as no permission for cafe_id = '{cafe_id}'.")
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
        updated_cafe = Cafe(
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
        if Cafe().find_by_name(updated_cafe.name) \
                and updated_cafe.name != cafe.name:
            # Duplicate cafe name, so tell then to stop copying....
            app.logger.debug(f"edit_cafe(): Detected duplicate cafe name '{updated_cafe.name}'.")
            Event().log_event("Edit Cafe Fail", f"Detected duplicate cafe name '{updated_cafe.name}'.")
            flash("Sorry, that name is already in use, choose another!")
            # Back to edit form
            return render_template("cafe_add.html", cafe=cafe, form=form, year=current_year)

        # ----------------------------------------------------------- #
        # Update details
        # ----------------------------------------------------------- #
        if Cafe().update_cafe(cafe_id, updated_cafe):
            # Flash back a message
            app.logger.debug(f"edit_cafe(): Successfully updated the cafe, cafe_id = '{cafe_id}'.")
            Event().log_event("Edit Cafe Success", f"Cafe updated '{updated_cafe.name}', cafe_id = '{cafe_id}'.")
            flash("The cafe details have been updated.")
        else:
            # Should never get here, but....
            app.logger.debug(f"edit_cafe(): Something went wrong with Cafe().update_cafe cafe_id = '{cafe_id}'.")
            Event().log_event("Edit Cafe Fail", f"Something went wrong. cafe_id = '{cafe_id}'.")
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
        updated_cafe = Cafe().one_cafe(cafe_id)
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
            app.logger.debug(f"edit_cafe(): Cafe has only moved {round(dist_km,1)} km, so no need to update GPXes.")

        # Back to cafe details page
        return redirect(url_for('cafe_details', cafe_id=cafe_id))

    # ----------------------------------------------------------- #
    # Handle GET
    # ----------------------------------------------------------- #

    # Flag as closed (if set)
    if not bool(cafe.active):
        flash("The cafe has been marked as closed / closing!")

    # Make sure cafe photo has correct path
    if cafe.image_name:
        cafe.image_name = f"/static/img/cafe_photos/{os.path.basename(cafe.image_name)}"
        app.logger.debug(f"cafe_detail(): cafe.image_name = '{cafe.image_name}'")

    # Show edit form for the specified cafe
    return render_template("cafe_add.html", cafe=cafe, form=form, year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# Mark a cafe as being closed
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/close_cafe/<int:cafe_id>", methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def close_cafe(cafe_id):
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    details = request.args.get('details', None)
    # cafe_id = request.args.get('cafe_id', None)
    # try:
    #     details = request.form['details']
    # except exceptions.BadRequestKeyError:
    #     details = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not cafe_id:
        app.logger.debug(f"close_cafe(): Missing cafe_id!")
        Event().log_event("Close Cafe Fail", f"Missing cafe_id")
        return abort(400)
    elif not details:
        app.logger.debug(f"close_cafe(): Missing details!")
        Event().log_event("Close Cafe Fail", f"Missing details")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = Cafe().one_cafe(cafe_id)

    if not cafe:
        app.logger.debug(f"close_cafe(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        Event().log_event("Close Cafe Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if not current_user.admin() \
            and current_user.email != cafe.added_email:
        # Failed authentication
        app.logger.debug(f"close_cafe(): Rejected request from '{current_user.email}' as no permissions"
                         f" for cafe.id = '{cafe.id}'.")
        Event().log_event("Close Cafe Fail", f"Rejected request from '{current_user.email}' as no permissions"
                          f" for cafe.id = '{cafe.id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Close the cafe
    # ----------------------------------------------------------- #
    if Cafe().close_cafe(cafe.id, details):
        # Success
        app.logger.debug(f"close_cafe(): Successfully closed the cafe, cafe.id = '{cafe.id}'.")
        Event().log_event("Close Cafe Success", f"Cafe marked as closed. cafe.id = '{cafe.id}'.")
        flash("Cafe marked as closed.")
    else:
        # Should never get here, but....
        app.logger.debug(f"close_cafe(): Cafe().close_cafe() failed with cafe.id = '{cafe.id}'.")
        Event().log_event("Close Cafe Fail", f"Cafe().close_cafe() failed with cafe.id = '{cafe.id}'.")
        flash("Sorry, something went wrong!")

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id))


# -------------------------------------------------------------------------------------------------------------- #
# Mark a cafe as not being closed
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/unclose_cafe", methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
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
        Event().log_event("unClose Cafe Fail", f"Missing cafe_id")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = Cafe().one_cafe(cafe_id)

    if not cafe:
        app.logger.debug(f"unclose_cafe(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        Event().log_event("unClose Cafe Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if not current_user.admin() \
            and current_user.email != cafe.added_email:
        # Failed authentication
        app.logger.debug(f"unclose_cafe(): Rejected request from '{current_user.email}' as no permissions"
                         f" for cafe.id = '{cafe.id}'.")
        Event().log_event("unClose Cafe Fail", f"Rejected request as no permissions. cafe_id = '{cafe_id}'")
        return abort(403)

    # ----------------------------------------------------------- #
    # Open the cafe
    # ----------------------------------------------------------- #
    if Cafe().unclose_cafe(cafe.id):
        # Success!
        app.logger.debug(f"unclose_cafe(): Successfully unclosed cafe with cafe_id = '{cafe_id}'.")
        Event().log_event("unClose Cafe Success", f"Successfully unclosed the cafe. cafe_id = '{cafe_id}'")
        flash("Cafe marked as open.")
    else:
        # Should never get here, but....
        app.logger.debug(f"unclose_cafe(): Cafe().unclose_cafe() failed with cafe_id = '{cafe_id}'.")
        Event().log_event("unClose Cafe Fail", f"Something went wrong. cafe_id = '{cafe_id}'")
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
def flag_cafe():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    cafe_id = request.args.get('cafe_id', None)
    reason = request.form['reason']
    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if reason == "":
        reason = " "

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not reason:
        app.logger.debug(f"flag_cafe(): Missing reason!")
        Event().log_event("Flag Cafe Fail", f"Missing reason!")
        return abort(400)
    elif not cafe_id:
        app.logger.debug(f"flag_cafe(): Missing cafe_id!")
        Event().log_event("Flag Cafe Fail", f"Missing cafe_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = Cafe().one_cafe(cafe_id)

    # Check id is valid
    if not cafe:
        app.logger.debug(f"flag_cafe(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        Event().log_event("Flag Cafe Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'")
        return abort(404)

    # ----------------------------------------------------------- #
    # Send a message to Admin
    # ----------------------------------------------------------- #
    message = Message(
        from_email=current_user.email,
        to_email=ADMIN_EMAIL,
        body=f"Cafe Objection to '{cafe.name}' (id={cafe.id}). Reason: {reason}"
    )

    if Message().add_message(message):
        # Success
        app.logger.debug(f"flag_cafe(): Flagged cafe, cafe_id = '{cafe_id}'.")
        Event().log_event("Flag Cafe Success", f"Flagged cafe, cafe_id = '{cafe_id}', reason = '{reason}'.")
        flash("Your message has been forwarded to an admin.")
    else:
        # Should never get here, but....
        app.logger.debug(f"flag_cafe(): Message().add_message failed, cafe_id = '{cafe_id}'.")
        Event().log_event("Flag Cafe Fail", f"Message().add_message failed, cafe_id = '{cafe_id}', reason = '{reason}'.")
        flash("Sorry, something went wrong.")

    # ----------------------------------------------------------- #
    # Alert admin via SMS
    # ----------------------------------------------------------- #
    # Threading won't have access to current_user, so need to acquire persistent user to pass on
    user = User().find_user_from_id(current_user.id)
    Thread(target=alert_admin_via_sms, args=(user, f"Cafe '{cafe.name}', Reason: '{reason}'",)).start()

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id))


# -------------------------------------------------------------------------------------------------------------- #
# Delete a comment
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/delete_comment", methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def delete_comment():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    comment_id = request.args.get('comment_id', None)
    cafe_id = request.args.get('cafe_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not comment_id:
        app.logger.debug(f"delete_comment(): Missing comment_id!")
        Event().log_event("Delete Comment Fail", f"Missing comment_id!")
        return abort(400)
    elif not cafe_id:
        app.logger.debug(f"delete_comment(): Missing cafe_id!")
        Event().log_event("Delete Comment Fail", f"Missing cafe_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    comment = CafeComment().get_comment(comment_id)
    cafe = Cafe().one_cafe(cafe_id)

    if not cafe:
        app.logger.debug(f"delete_comment(): Failed to locate cafe with cafe_id = '{cafe_id}'.")
        Event().log_event("Delete Comment Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'.")
        return abort(404)

    # Check comment id is valid
    if not comment:
        app.logger.debug(f"delete_comment(): Failed to locate comment with comment_id = '{comment_id}'.")
        Event().log_event("Delete Comment Fail", f"Failed to locate comment with comment_id = '{comment_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if not current_user.admin() \
            and current_user.email != comment.email:
        # Failed authentication
        app.logger.debug(f"delete_comment(): Rejected request from '{current_user.email}' as no permissions"
                         f" for comment_id = '{comment_id}'.")
        Event().log_event("Delete Comment Fail", f"Rejected request from user '{current_user.email}' as no "
                                                 f"permissions for comment_id = '{comment_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Delete comment
    # ----------------------------------------------------------- #
    if CafeComment().delete_comment(comment_id):
        # Success
        app.logger.debug(f"delete_comment(): Successfully deleted the comment, comment_id = '{comment_id}'.")
        Event().log_event("Delete Comment Success", f"Successfully deleted the comment. comment_id = '{comment_id}''.")
        flash("Comment deleted.")
    else:
        # Should never get here, but....
        app.logger.debug(f"delete_comment(): Failed to delete the comment, comment_id = '{comment_id}'.")
        Event().log_event("Delete Comment Fail", f"Failed to delete the comment, comment_id = '{comment_id}'.")
        flash("Sorry, something went wrong!")

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id))
