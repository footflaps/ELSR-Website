from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import date
from flask_googlemaps import Map
from werkzeug import exceptions
import gpxpy
import gpxpy.gpx
import mpu
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS, dynamic_map_size, current_year


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe, CreateCafeForm, UpdateCafeForm, OPEN_CAFE_ICON, CLOSED_CAFE_ICON
from core.dB_cafe_comments import CafeComment, CreateCafeCommentForm
from core.routes_gpx import check_new_cafe_with_all_gpxes
from core.dB_gpx import Gpx
from core.routes_gpx import MIN_DISPLAY_STEP_KM
from core.db_messages import Message, ADMIN_EMAIL
from core.dB_events import Event
from core.db_users import update_last_seen, logout_barred_user


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

# -------------------------------------------------------------------------------------------------------------- #
# Constants used for uploading pictures of the cafes
# -------------------------------------------------------------------------------------------------------------- #

IMAGE_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
CAFE_FOLDER = os.environ['ELSR_CAFE_FOLDER']


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
    return render_template("cafe_list.html", year=current_year, cafes=cafes, cafemap=cafemap)


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
        Event().log_event("Cafe Fail", f"Failed to locate cafe with cafe.id = '{cafe_id}'.")
        print(f"cafe_details(): Failed to locate cafe with cafe.id = {cafe_id}")
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
            Event().log_event("Cafe Comment Success", f"Comment posted successfully cafe.id = '{cafe.id}'.")
            print("Comment posted successfully!")
        else:
            Event().log_event("Cafe Comment Fail", f"Comment post failed.")
            print("Comment post failed!")

        # We can't reset form, so to show the post completed, we have to redirect
        # back to the start of ourselves.
        return redirect(url_for('cafe_details', cafe_id=cafe.id))

    elif request.method == 'POST':

        # This traps a post, but where the form verification failed.
        flash("Comment failed to post - did you write anything?")

        # Flag as closed
        if not bool(cafe.active):
            flash("The cafe has been marked as closed / closing!")

        # Render using cafe details template
        return render_template("cafe_details.html", cafe=cafe, form=form, comments=comments, year=current_year,
                               cafemap=cafemap, gpxes=gpxes, gpxmap=gpxmap)

    else:

        # ----------------------------------------------------------- #
        # Handle GET
        # ----------------------------------------------------------- #

        # Flag as closed
        if not bool(cafe.active):
            flash("The cafe has been marked as closed / closing!")

        # Render using cafe details template
        return render_template("cafe_details.html", cafe=cafe, form=form, comments=comments, year=current_year,
                               cafemap=cafemap, gpxes=gpxes, gpxmap=gpxmap)


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
        print(f"new_cafe(): Range is {round(range_km, 1)}km")
        if range_km > ELSR_MAX_KM:
            # Too far out of range from Cambridge
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
            Event().log_event("New Cafe Fail", f"Detected duplicate cafe name '{new_cafe.name}'.")
            print(f"new_cafe(): Detected duplicate cafe name '{new_cafe.name}'.")
            flash("Sorry, that name is already in use, choose another!")
            # Back to edit form
            return render_template("cafe_add.html", form=form, cafe=None, year=current_year)

        # ----------------------------------------------------------- #
        #   Try to add the cafe
        # ----------------------------------------------------------- #
        if Cafe().add_cafe(new_cafe):
            Event().log_event("New Cafe Success", f"Cafe {new_cafe.name} has been added!")
            flash(f"Cafe {new_cafe.name} has been added!")
        else:
            Event().log_event("New Cafe Fail", f"Something went wrong! '{new_cafe.name}'.")
            print(f"new_cafe(): Cafe add failed.")
            flash("Sorry, something went wrong.")
            # Back to edit form
            return render_template("cafe_add.html", form=form, cafe=None, year=current_year)

        # ----------------------------------------------------------- #
        #   Look up our new cafe
        # ----------------------------------------------------------- #
        # Look up our new cafe in the dB as we can't know its ID until after it's been added
        cafe = Cafe().find_by_name(new_cafe.name)
        print(f"new_cafe(): Cafe added, cafe_id = {cafe.id}")

        # ----------------------------------------------------------- #
        #   Update GPX routes with new cafe etc
        # ----------------------------------------------------------- #
        check_new_cafe_with_all_gpxes(cafe)
        flash(f"All GPX routes have been updated with distance to {cafe.name}.")

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
        Event().log_event("Edit Cafe Fail", f"Missing cafe_id!.")
        print(f"edit_cafe(): Missing cafe_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = Cafe().one_cafe(cafe_id)

    # Check id is valid
    if not cafe:
        Event().log_event("Edit Cafe Fail", f"Failed to locate cafe with cafe_id = '{cafe_id}'.")
        print(f"edit_cafe(): Failed to locate cafe with cafe_id = '{cafe_id}'")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if not current_user.admin() \
            and current_user.email != cafe.added_email:
        # Failed authentication
        Event().log_event("Edit Cafe Fail", f"Rejected request as no permission for cafe_id = '{cafe_id}'.")
        print(f"edit_cafe(): Rejected request for {current_user.email} as no permissions")
        return abort(403)

    # ----------------------------------------------------------- #
    # Need a form for the cafe details
    # ----------------------------------------------------------- #

    form = UpdateCafeForm(
        name=cafe.name,
        lat=cafe.lat,
        lon=cafe.lon,
        website_url=cafe.website_url,
        summary=cafe.summary,
        rating=cafe.rating,
        detail=cafe.details
    )

    # ----------------------------------------------------------- #
    # Handle POST requests (two different entry points)
    # ----------------------------------------------------------- #

    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        # Entry method #1 - form submitted successfully
        # ----------------------------------------------------------- #

        print(f"edit_cafe(): acting on form.validate_on_submit")

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
            Event().log_event("Edit Cafe Fail", f"Detected duplicate cafe name '{updated_cafe.name}', "
                                                f"cafe_id = '{cafe_id}'.")
            print(f"edit_cafe(): Detected duplicate cafe name '{updated_cafe.name}'.")
            flash("Sorry, that name is already in use, choose another!")
            # Back to edit form
            return render_template("cafe_add.html", cafe=cafe, form=form, year=current_year)

        # ----------------------------------------------------------- #
        # Update details
        # ----------------------------------------------------------- #
        if Cafe().update_cafe(cafe_id, updated_cafe):
            # Flash back a message
            Event().log_event("Edit Cafe Success", f"Cafe updated '{updated_cafe.name}', cafe_id = '{cafe_id}'.")
            flash("The cafe details have been updated.")
            print(f"edit_cafe(): Successfully updated the cafe.")
        else:
            Event().log_event("Edit Cafe Fail", f"Something went wrong. cafe_id = '{cafe_id}'.")
            flash("Sorry, something went wrong!")
            print(f"edit_cafe(): Failed to update the cafe.")

        # ----------------------------------------------------------- #
        #   Update GPX routes with new cafe etc
        # ----------------------------------------------------------- #
        updated_cafe = Cafe().one_cafe(cafe_id)
        print(f"edit_cafe(): calling check_new_cafe_with_all_gpxes for {updated_cafe.name}")
        check_new_cafe_with_all_gpxes(updated_cafe)
        flash(f"All GPX routes have been updated with distance to {updated_cafe.name}.")

        # Back to cafe details page
        return redirect(url_for('cafe_details', cafe_id=cafe_id))

    elif request.method == 'POST':

        # ----------------------------------------------------------- #
        # Entry method #2 - POSTing filename back (uploading photo)
        # ----------------------------------------------------------- #

        print(f"edit_cafe(): acting on request.method == 'POST'")

        # We get here for two reasons:
        #  1. The photo was updated using POST
        #  2. The form was submitted, but failed validation

        # Did we get passed the filename for the photo?
        if 'input_file' not in request.files:
            # Almost certain the form failed validation
            Event().log_event("Edit Cafe Fail", f"Something missing in the form submission. cafe_id = '{cafe_id}'.")
            flash("There was something missing in the form submission, see below for details.")
            return render_template("cafe_add.html", cafe=cafe, form=form, year=current_year)

        else:
            # Get the filename
            file = request.files['input_file']
            print(f"new_cafe(): Uploaded '{file}'")

            file = request.files['input_file']
            # If the user does not select a file, the browser submits an
            # empty file without a filename.
            if file.filename == '':
                Event().log_event("Edit Cafe Fail", f"No selected file. cafe_id = '{cafe_id}'.")
                flash('No selected file')
                return redirect(request.url)
            if file:
                if allowed_file(file.filename):
                    filename = f"cafe_{cafe.id}.jpg"
                    file.save(os.path.join(CAFE_FOLDER, filename))
                    print("new_cafe(): All ok")
                    # Update cafe object with filename
                    if Cafe().update_photo(cafe.id, f"/static/img/cafe_photos/{filename}"):
                        Event().log_event("Edit Cafe Pass", f"Cafe photo updated. cafe_id = '{cafe_id}'.")
                        flash("Cafe photo has been updated.")
                        print(f"edit_cafe(): Successfully updated the photo.")
                    else:
                        Event().log_event("Edit Cafe Fail", f"Something went wrong. cafe_id = '{cafe_id}'.")
                        flash("Sorry, something went wrong!")
                        print(f"edit_cafe(): Failed to update the photo.")
                else:
                    Event().log_event("Edit Cafe Fail", f"Invalid image filename. file.filename = '{file.filename}'.")
                    flash("Invalid file type for image!")
                    print(f"edit_cafe(): Invalid file type for image.")

            # Show the updated cafe in the details page
            return redirect(url_for('cafe_details', cafe_id=cafe_id))

    # ----------------------------------------------------------- #
    # Handle GET
    # ----------------------------------------------------------- #

    # Flag as closed (if set)
    if not bool(cafe.active):
        flash("The cafe has been marked as closed / closing!")

    # Show edit form for the specified cafe
    return render_template("cafe_add.html", cafe=cafe, form=form, year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# Mark a cafe as being closed
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/close_cafe", methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
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
        Event().log_event("Close Cafe Fail", f"Missing cafe_id")
        print(f"close_cafe(): Missing cafe_id!")
        return abort(400)
    elif not details:
        Event().log_event("Close Cafe Fail", f"Missing details")
        print(f"close_cafe(): Missing details!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = Cafe().one_cafe(cafe_id)

    if not cafe:
        Event().log_event("Close Cafe Fail", f"Failed to locate cafe with cafe.id = '{cafe.id}'.")
        print(f"close_cafe(): Failed to locate cafe with cafe.id = {cafe.id}")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if not current_user.admin() \
            and current_user.email != cafe.added_email:
        # Failed authentication
        Event().log_event("Close Cafe Fail", f"Rejected request as no permissions. cafe.id = '{cafe.id}'.")
        print("close_cafe(): Rejected request as no permissions")
        return abort(403)

    # ----------------------------------------------------------- #
    # Close the cafe
    # ----------------------------------------------------------- #
    if Cafe().close_cafe(cafe.id, details):
        Event().log_event("Close Cafe Pass", f"Cafe marked as closed. cafe.id = '{cafe.id}'.")
        flash("Cafe marked as closed.")
        print(f"close_cafe(): Successfully closed the cafe.")
    else:
        Event().log_event("Close Cafe Fail", f"Something went wrong. cafe.id = '{cafe.id}'.")
        flash("Sorry, something went wrong!")
        print(f"close_cafe(): Failed to close the cafe.")

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id))


# -------------------------------------------------------------------------------------------------------------- #
# Mark a cafe as not being closed
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/unclose_cafe", methods=['GET', 'POST'])
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
        Event().log_event("unClose Cafe Fail", f"Missing cafe_id")
        print(f"unclose_cafe(): Missing cafe_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = Cafe().one_cafe(cafe_id)

    if not cafe:
        Event().log_event("unClose Cafe Fail", f"Failed to locate cafe with cafe.id = '{cafe.id}'")
        print(f"unclose_cafe(): Failed to locate cafe with cafe.id = {cafe.id}")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if not current_user.admin() \
            and current_user.email != cafe.added_email:
        # Failed authentication
        Event().log_event("unClose Cafe Fail", f"Rejected request as no permissions. cafe.id = '{cafe.id}'")
        print("unclose_cafe(): Rejected request as no permissions")
        return abort(403)

    # ----------------------------------------------------------- #
    # Open the cafe
    # ----------------------------------------------------------- #
    if Cafe().unclose_cafe(cafe.id):
        # Flash back a message
        Event().log_event("unClose Cafe Success", f"Successfully unclosed the cafe. cafe.id = '{cafe.id}'")
        flash("Cafe marked as open.")
        print(f"unclose_cafe(): Successfully unclosed the cafe.")
    else:
        Event().log_event("unClose Cafe Fail", f"Something went wrong. cafe.id = '{cafe.id}'")
        flash("Sorry, something went wrong!")
        print(f"unclose_cafe(): Failed to unclose the cafe.")

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id))


# -------------------------------------------------------------------------------------------------------------- #
# Flag a cafe to an admin
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/flag_cafe", methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def flag_cafe():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    cafe_id = request.args.get('cafe_id', None)
    try:
        reason = request.form['reason']
    except exceptions.BadRequestKeyError:
        reason = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not reason:
        Event().log_event("Flag Cafe Fail", f"Missing reason!")
        print(f"flag_cafe(): Missing reason!")
        return abort(400)
    elif not cafe_id:
        Event().log_event("Flag Cafe Fail", f"Missing cafe_id!")
        print(f"flag_cafe(): Missing cafe_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    cafe = Cafe().one_cafe(cafe_id)

    # Check id is valid
    if not cafe:
        Event().log_event("Flag Cafe Fail", f"Failed to locate cafe with cafe.id = '{cafe.id}'")
        print(f"flag_cafe(): Failed to locate cafe with cafe.id = {cafe.id}")
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
        Event().log_event("Flag Cafe Success", f"Flagged cafe, cafe.id = '{cafe.id}'")
        print(f"flag_cafe(): flagged cafe {cafe_id} for '{reason}'")
        flash("Your message has been forwarded to an admin.")
    else:
        Event().log_event("Flag Cafe Fail", f"Failed to flag cafe {cafe_id} for '{reason}'")
        print(f"flag_cafe(): Failed to flag cafe {cafe_id} for '{reason}'")
        flash("Sorry, something went wrong.")

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id))


# -------------------------------------------------------------------------------------------------------------- #
# Delete a comment
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/delete_comment", methods=['GET', 'POST'])
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
        Event().log_event("Delete Comment Fail", f"Missing commend_id!")
        print(f"delete_comment(): Missing commend_id!")
        return abort(400)
    elif not cafe_id:
        Event().log_event("Delete Comment Fail", f"Missing cafe_id!")
        print(f"delete_comment(): Missing cafe_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    comment = CafeComment().get_comment(comment_id)
    cafe = Cafe().one_cafe(cafe_id)

    if not cafe:
        Event().log_event("Delete Comment Fail", f"Failed to locate cafe with cafe.id = '{cafe.id}'")
        print(f"delete_comment(): Failed to locate cafe with cafe.id = '{cafe.id}'")
        return abort(404)

    # Check comment id is valid
    if not comment:
        Event().log_event("Delete Comment Fail", f"Failed to locate comment with comment.id = '{comment.id}'")
        print(f"delete_comment(): Failed to locate comment with comment.id = '{comment.id}'")
        return abort(404)

    print(current_user.email, comment.email, current_user.admin())

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if not current_user.admin() \
            and current_user.email != comment.email:
        # Failed authentication
        Event().log_event("Delete Comment Fail", f"Rejected request from user '{current_user.email}' as no"
                                                 f" permissions for comment.id = '{comment.id}'")
        print(f"delete_comment(): Rejected request from user {current_user.email} as no permissions")
        return abort(403)

    # ----------------------------------------------------------- #
    # Delete comment
    # ----------------------------------------------------------- #
    if CafeComment().delete_comment(comment_id):
        # Flash back a message
        Event().log_event("Delete Comment Success", f"Successfully deleted the comment. comment.id = '{comment.id}'")
        flash("Comment deleted.")
        print(f"delete_comment(): Successfully deleted the comment.")
    else:
        Event().log_event("Delete Comment Fail", f"Something went wrong. comment.id = '{comment.id}'")
        flash("Sorry, something went wrong!")
        print(f"delete_comment(): Failed to delete the comment.")

    # Back to cafe details page
    return redirect(url_for('cafe_details', cafe_id=cafe_id))
