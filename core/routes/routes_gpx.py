from flask import render_template, redirect, url_for, flash, request, abort, send_from_directory, Response, make_response
from flask_login import current_user
from werkzeug import exceptions
import os
from threading import Thread
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS, current_year, delete_file_if_exists, is_mobile, live_site

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.user_repository import UserModel, UserRepository
from core.database.repositories.gpx_repository import GpxModel, GpxRepository
from core.database.repositories.cafe_repository import CafeRepository
from core.database.repositories.event_repository import EventRepository
from core.database.repositories.message_repository import MessageModel, MessageRepository, ADMIN_EMAIL
from core.database.repositories.calendar_repository import CalendarRepository

from core.database.jinja.user_jinja import get_user_name


from core.forms.gpx_forms import UploadGPXForm

from core.subs_gpx import allowed_file
from core.subs_google_maps import polyline_json, markers_for_cafes_native, MAP_BOUNDS, google_maps_api_key, \
                                  count_map_loads
from core.subs_gpx_edit import check_route_name, strip_excess_info_from_gpx
from core.subs_graphjs import get_elevation_data, get_cafe_heights_from_gpx
from core.subs_email import send_message_notification_email
from core.subs_sms import alert_admin_via_sms

from core.decorators.user_decorators import update_last_seen, logout_barred_user, login_required, rw_required


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def download_count(gpx):
    # Add counts
    if gpx.downloads:
        try:
            return len(json.loads(gpx.downloads))
        except:
            return 0
    else:
        return 0


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# List of all known GPX files
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/routes', methods=['GET'])
@update_last_seen
def gpx_list() -> Response | str:
    # ----------------------------------------------------------- #
    # Grab all our routes
    # ----------------------------------------------------------- #
    gpxes: list[GpxModel] = GpxRepository.all_gpxes()

    # ----------------------------------------------------------- #
    # Grab all our users
    # ----------------------------------------------------------- #
    users: list[UserRepository] = UserRepository.all_users()

    # Double check we have all the files present
    missing_files: list[int] = []

    # ----------------------------------------------------------- #
    # Look through GPXes looking for missing files and converting users
    # ----------------------------------------------------------- #
    for gpx in gpxes:

        gpx.user_name = next((user.name for user in users if user.email == gpx.email), "Unkown")

        # Absolute path name
        filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
        # Check the file is actually there, before we try and parse it etc
        if not os.path.exists(filename):
            missing_files.append(gpx.id)

    # Need different path for Admin
    if not current_user.is_authenticated:
        admin: bool = False
    elif current_user.admin:
        admin = True
    else:
        admin = False

    # ----------------------------------------------------------- #
    # Render page
    # ----------------------------------------------------------- #
    if admin:
        for missing in missing_files:
            flash(f"We are missing the GPX file for route {missing}!")

    return render_template("gpx_list.html", year=current_year, gpxes=gpxes, mobile=is_mobile(), live_site=live_site(),
                           missing_files=missing_files)


# -------------------------------------------------------------------------------------------------------------- #
# List of top 10 most downloaded GPXes
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_top10', methods=['GET'])
@update_last_seen
def gpx_top10() -> Response | str:
    # Grab all our gpxes
    gpxes = GpxRepository.all_gpxes_sorted_downloads()

    # Convert JSON field into int
    for gpx in gpxes:
        gpx.num_downloads = download_count(gpx)

    # Render template
    return render_template("gpx_top10.html", year=current_year, gpxes=gpxes, mobile=is_mobile(), live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Display a single GPX file
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/route/<int:gpx_id>', methods=['GET'])
@update_last_seen
def gpx_details(gpx_id: int) -> Response | str:
    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = GpxRepository.one_by_id(gpx_id)
    if not gpx:
        app.logger.debug(f"gpx_details(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        EventRepository.log_event("One GPX Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Route must be public
    # Tortuous logic as a non-logged-in user doesn't have any of our custom attributes eg email etc
    if not gpx.public and \
            not current_user.is_authenticated:
        app.logger.debug(f"gpx_details(): Refusing permission for non logged in user and hidden route '{gpx_id}'.")
        EventRepository.log_event("One GPX Fail", f"Refusing permission for non logged in user and hidden route '{gpx_id}'.")
        return redirect(url_for('not_logged_in'))   # type: ignore

    elif not gpx.public and \
            current_user.email != gpx.email and \
            not current_user.admin:
        app.logger.debug(f"gpx_details(): Refusing permission for user '{current_user.email}' to see "
                         f"hidden GPX route '{gpx.id}'!")
        EventRepository.log_event("One GPX Fail", f"Refusing permission for user {current_user.email} to see "
                                          f"hidden GPX route, gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Get info for webpage
    # ----------------------------------------------------------- #
    author = UserRepository.one_by_email(gpx.email).name
    cafe_list = CafeRepository.cafes_passed_by_gpx(gpx.cafes_passed)

    # ----------------------------------------------------------- #
    # Double check GPX file actually exists
    # ----------------------------------------------------------- #

    # This is the absolute path to the file
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

    # Check the file is actually there, before we try and parse it etc
    if not os.path.exists(filename):
        # Should never happen, but may as well handle it cleanly

        # Need different path for Admin
        if not current_user.is_authenticated:
            admin = False
        elif current_user.admin:
            admin = True
        else:
            admin = False

        if admin:
            # Admin needs to be able to rectify the situation
            app.logger.debug(f"gpx_details(): Can't find '{filename}'!")
            EventRepository.log_event("One GPX Fail", f"Can't find '{filename}'!")
            flash("Sorry, we seem to have lost that GPX file!")
        else:
            # Non admin just gets a Dear John...
            app.logger.debug(f"gpx_details(): Can't find '{filename}'!")
            EventRepository.log_event("One GPX Fail", f"Can't find '{filename}'!")
            flash("Sorry, we seem to have lost that GPX file!")
            flash("Someone should probably fire the web developer...")
            return abort(404)

    # ----------------------------------------------------------- #
    # Need direction (CW / CCW)
    # ----------------------------------------------------------- #
    if gpx.direction == "CW":
        gpx.direction = "Clockwise"
    elif gpx.direction == "CCW":
        gpx.direction = "Anti-clockwise"
    else:
        gpx.direction = "n/a"

    # ----------------------------------------------------------- #
    # Need path as weird Google proprietary JSON string thing
    # ----------------------------------------------------------- #
    if os.path.exists(filename):
        polyline = polyline_json(filename)
    else:
        polyline = {
            'polyline': [],
            'midlat': 52.2,
            'midlon': 0.13,
        }

    # ----------------------------------------------------------- #
    # Need cafe markers as weird Google proprietary JSON string
    # ----------------------------------------------------------- #
    cafe_markers = markers_for_cafes_native(cafe_list)

    # ----------------------------------------------------------- #
    # Get elevation data
    # ----------------------------------------------------------- #
    if os.path.exists(filename):
        elevation_data = get_elevation_data(filename)
        cafe_elevation_data = get_cafe_heights_from_gpx(cafe_list, elevation_data)
    else:
        elevation_data = []
        cafe_elevation_data = []

    # ----------------------------------------------------------- #
    # Is this GPX in the calendar as a ride or rides
    # ----------------------------------------------------------- #
    # If the route in attached to a ride in the Calendar, then they can't hide it as it would break the ride
    rides = CalendarRepository.all_rides_gpx_id(gpx.id)

    # ----------------------------------------------------------- #
    # Num downloads
    # ----------------------------------------------------------- #
    gpx.num_downloads = download_count(gpx)

    # ----------------------------------------------------------- #
    # Flag if hidden
    # ----------------------------------------------------------- #
    if not gpx.public:
        flash("This route is not public yet!")

    # Keep count of Google Map Loads
    count_map_loads(1)

    # Render in main index template
    return render_template("gpx_details.html", gpx=gpx, year=current_year, cafe_markers=cafe_markers,
                           author=author, cafe_list=cafe_list, elevation_data=elevation_data,
                           cafe_elevation_data=cafe_elevation_data, GOOGLE_MAPS_API_KEY=google_maps_api_key(),
                           polyline=polyline['polyline'], midlat=polyline['midlat'], midlon=polyline['midlon'],
                           MAP_BOUNDS=MAP_BOUNDS, rides=rides, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Add a GPX ride to the dB
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/new_route', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def new_route() -> Response | str:
    # ----------------------------------------------------------- #
    # Need a form for uploading
    # ----------------------------------------------------------- #
    form = UploadGPXForm()

    # Are we posting the completed form?
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        #   POST - form submitted and validated
        # ----------------------------------------------------------- #

        # Try and get the filename.
        if 'filename' not in request.files:
            # Almost certain the form failed validation
            app.logger.debug(f"new_route(): Failed to find 'filename' in request.files!")
            EventRepository.log_event(f"New GPX Fail", f"Failed to find 'filename' in request.files!")
            flash("Couldn't find the file.")
            return render_template("gpx_add.html", year=current_year, form=form, live_site=live_site())

        else:
            # Get the filename
            file = request.files['filename']
            app.logger.debug(f"new_route(): About to upload '{file}'.")

            # If the user does not select a file, the browser submits an
            # empty file without a filename.
            if file.filename == '':
                app.logger.debug(f"new_route(): No selected file!")
                EventRepository.log_event(f"New GPX Fail", f"No selected file!")
                flash('No selected file')
                return render_template("gpx_add.html", year=current_year, form=form, live_site=live_site())

            if not file or \
                    not allowed_file(file.filename):
                app.logger.debug(f"new_route(): Invalid file '{file.filename}'!")
                EventRepository.log_event(f"New GPX Fail", f"Invalid file '{file.filename}'!")
                flash("That's not a GPX file!")
                return render_template("gpx_add.html", year=current_year, form=form, live_site=live_site())

            # Create a new GPX object
            # We do this first as we need the id in order to create
            # the filename for the GPX file when we upload it
            gpx: GpxModel = GpxModel()
            gpx.name = form.name.data
            gpx.email = current_user.email
            gpx.cafes_passed = "[]"
            gpx.ascent_m = 0
            gpx.length_km = 0
            gpx.filename = "tmp"
            gpx.type = form.type.data
            gpx.details = form.details.data
            gpx.public = False

            # Add to the dB
            gpx = GpxRepository.add_gpx(gpx)  # type: ignore
            if gpx:
                # Success, added GPX to dB
                app.logger.debug(f"new_route(): GPX added to dB, id = '{gpx.id}'.")
                EventRepository.log_event(f"New GPX Success", f" GPX added to dB, gpx.id = '{gpx.id}'.")
            else:
                # Failed to create new dB entry
                app.logger.debug(f"new_route(): Failed to add gpx to the dB!")
                EventRepository.log_event(f"New GPX Fail", f"Failed to add gpx to the dB!")
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form, live_site=live_site())

            # This is where we will store it
            filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, f"gpx_{gpx.id}.gpx")
            app.logger.debug(f"new_route(): Filename will be = '{filename}'.")

            # Make sure this doesn't already exist
            if not delete_file_if_exists(filename):
                # Failed to delete existing file (func will generate error trace)
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form, live_site=live_site())

            # Upload the GPX file
            try:
                file.save(filename)
            except Exception as e:
                app.logger.debug(f"new_route(): Failed to upload/save '{filename}', error code was {e.args}.")
                EventRepository.log_event(f"New GPX Fail", f"Failed to upload/save '{filename}', error code was {e.args}.")
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form, live_site=live_site())

            # Update gpx object with filename
            if not GpxRepository.update_filename(gpx.id, filename):
                app.logger.debug(f"new_route(): Failed to update filename in the dB for gpx_id='{gpx.id}'.")
                EventRepository.log_event(f"New GPX Fail", f"Failed to update filename in the dB for gpx_id='{gpx.id}'.")
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form, live_site=live_site())

            # Strip all excess data from the file
            flash("Any HR or Power data has been removed.")
            strip_excess_info_from_gpx(filename, gpx.id, f"ELSR: {gpx.name}")

            # Forward to edit route as that's the next step
            app.logger.debug(f"new_route(): New GPX added, gpx_id = '{gpx.id}', ({gpx.name}).")
            EventRepository.log_event(f"New GPX Success", f"New GPX added, gpx_id = '{gpx.id}', ({gpx.name}).")
            return redirect(url_for('edit_route', gpx_id=gpx.id))   # type: ignore

    elif request.method == 'POST':

        # ----------------------------------------------------------- #
        #   POST - form validation failed
        # ----------------------------------------------------------- #
        flash("Form not filled in properly, see below!")

        return render_template("gpx_add.html", year=current_year, form=form, live_site=live_site())

    # ----------------------------------------------------------- #
    #   GET - render form etc
    # ----------------------------------------------------------- #

    return render_template("gpx_add.html", year=current_year, form=form, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Delete a GPX route
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_delete', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def route_delete() -> Response | str:
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)
    try:
        return_page = request.form['return_page']
    except exceptions.BadRequestKeyError:
        return_page = None
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
    if not gpx_id:
        app.logger.debug(f"route_delete(): Missing gpx_id!")
        EventRepository.log_event("GPX Delete Fail", f"Missing gpx_id!")
        return abort(400)
    elif not password:
        app.logger.debug(f"route_delete(): Missing Password!")
        EventRepository.log_event("GPX Delete Fail", f"Missing Password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = GpxRepository.one_by_id(gpx_id)

    if not gpx:
        app.logger.debug(f"route_delete(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        EventRepository.log_event("GPX Delete Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access to Admin or Author
    # ----------------------------------------------------------- #
    if current_user.email != gpx.email \
            and not current_user.admin:
        app.logger.debug(f"route_delete(): Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        EventRepository.log_event("GPX Delete Fail", f"Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    #  Validate password
    # ----------------------------------------------------------- #
    # Need current user
    user: UserModel | None = UserRepository.one_by_id(current_user.id)

    # Validate against current_user's password
    if not UserRepository.validate_password(user, password, user_ip):
        app.logger.debug(f"route_delete(): Delete failed, incorrect password for user_id = '{user.id}'!")
        EventRepository.log_event("GPX Delete Fail", f"Incorrect password for user_id = '{user.id}'!")
        flash(f"Incorrect password for user {user.name}!")
        # Go back to route detail page
        return redirect(url_for('gpx_details', gpx_id=gpx_id))  # type: ignore

    # ----------------------------------------------------------- #
    # Delete #1: Remove from dB
    # ----------------------------------------------------------- #
    if GpxRepository.delete_gpx(gpx.id):
        app.logger.debug(f"route_delete(): Success, gpx_id = '{gpx_id}'.")
        EventRepository.log_event("GPX Delete Success", f"Successfully deleted GPX from dB, gpx_id = {gpx_id}!")
        flash("Route was deleted!")
    else:
        # Should never get here, but..
        app.logger.debug(f"route_delete(): Gpx().delete_gpx(gpx.id) failed for gpx.id = '{gpx.id}'.")
        EventRepository.log_event("GPX Delete Fail", f"Gpx().delete_gpx(gpx.id) failed for gpx.id = '{gpx.id}'.")
        flash("Sorry, something went wrong!")
        # Back to GPX list page
        return redirect(url_for('gpx_list'))  # type: ignore

    # ----------------------------------------------------------- #
    # Delete #2: Remove GPX file itself
    # ----------------------------------------------------------- #
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
    try:
        os.remove(filename)
        app.logger.debug(f"route_delete(): File '{filename}' deleted from directory.")
    except Exception as e:
        app.logger.debug(f"route_delete(): Failed to delete GPX file '{filename}', error code was '{e.args}'.")
        EventRepository.log_event("GPX Delete Fail", f"Failed to delete GPX file '{filename}', "
                                             f"error code was {e.args}, gpx_id = {gpx_id}!")

    # Back to GPX list page
    return redirect(url_for('gpx_list'))  # type: ignore


# -------------------------------------------------------------------------------------------------------------- #
# Flag a gpx to an admin
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/flag_gpx", methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def flag_gpx() -> Response | str:
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)
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
        app.logger.debug(f"flag_gpx(): Missing reason!")
        EventRepository.log_event("Flag GPX Fail", f"Missing reason!")
        return abort(400)
    elif not gpx_id:
        app.logger.debug(f"flag_gpx(): Missing gpx_id!")
        EventRepository.log_event("Flag GPX Fail", f"Missing gpx_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = GpxRepository.one_by_id(gpx_id)
    if not gpx:
        app.logger.debug(f"flag_gpx(): Failed to locate GPX with gpx_id = '{gpx_id}' in dB.")
        EventRepository.log_event("Flag GPX Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}' in dB.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Send a message to Admin
    # ----------------------------------------------------------- #
    message = MessageModel(
        from_email=current_user.email,
        to_email=ADMIN_EMAIL,
        body=f"GPX Objection to '{gpx.name}' (id={gpx.id}). Reason: {reason}"
    )

    if MessageRepository.add_message(message):
        # Success
        send_message_notification_email(message, current_user)
        app.logger.debug(f"flag_gpx(): Flagged GPX, gpx_id = '{gpx_id}'.")
        EventRepository.log_event("Flag GPX Success", f"Flagged GPX, gpx_id = '{gpx_id}', reason = '{reason}'.")
        flash("Your message has been forwarded to an admin.")
    else:
        # Should never get here, but....
        app.logger.debug(f"flag_gpx(): Message().add_message failed, gpx_id = '{gpx_id}'.")
        EventRepository.log_event("Flag GPX Fail", f"Message().add_message failed, gpx_id = '{gpx_id}', reason = '{reason}'.")
        flash("Sorry, something went wrong.")

    # ----------------------------------------------------------- #
    # Alert admin via SMS
    # ----------------------------------------------------------- #
    # Threading won't have access to current_user, so need to acquire persistent user to pass on
    user: UserModel | None = UserRepository.one_by_id(current_user.id)
    Thread(target=alert_admin_via_sms, args=(user, f"GPX '{gpx.name}', Reason: '{reason}'",)).start()

    # Back to GPX details page
    return redirect(url_for('gpx_details', gpx_id=gpx_id))  # type: ignore


# -------------------------------------------------------------------------------------------------------------- #
# Download a GPX route (logged in user)
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_download/<int:gpx_id>', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def route_download(gpx_id) -> Response | str:
    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = GpxRepository.one_by_id(gpx_id)
    if not gpx:
        app.logger.debug(f"route_download(): Failed to locate GPX with gpx_id = '{gpx_id}' in dB.")
        EventRepository.log_event("GPX Download Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        flash("Sorry, we couldn't find that GPX file in the database!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check GPX file exists
    # ----------------------------------------------------------- #
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
    if not os.path.exists(filename):
        # Should never get here, but..
        app.logger.debug(f"route_download(): Failed to locate filename = '{filename}', gpx_id = '{gpx_id}'.")
        EventRepository.log_event("GPX Download Fail", f"Failed to locate filename = '{filename}', gpx_id = '{gpx_id}'.")
        flash("Sorry, we couldn't find that GPX file on the server!")
        flash("You should probably fire the web developer...")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check GPX is public
    # ----------------------------------------------------------- #
    if not gpx.public:
        owner_name = get_user_name(gpx.email)
        app.logger.debug(f"route_download(): Private GPX, gpx_id = '{gpx_id}' in dB.")
        EventRepository.log_event("GPX Download Fail", f"Private GPX, GPX with gpx_id = '{gpx_id}'.")
        flash(f"Sorry, that GPX file has been marked as Private by '{owner_name}'")
        return abort(404)

    # ----------------------------------------------------------- #
    # Update the GPX file with the correct name (in case it's changed)
    # ----------------------------------------------------------- #
    check_route_name(gpx)

    # ----------------------------------------------------------- #
    # Update count
    # ----------------------------------------------------------- #
    GpxRepository.update_downloads(gpx.id, current_user.email)

    # ----------------------------------------------------------- #
    # Send link to download the file
    # ----------------------------------------------------------- #

    # This is the filename the user will see
    download_name = f"ELSR_{gpx.name.replace(' ', '_')}.gpx"

    app.logger.debug(f"route_download(): Serving GPX gpx_id = '{gpx_id}' ({gpx.name}) to '{current_user.email}', "
                     f"filename = '{filename}'.")
    EventRepository.log_event("GPX Downloaded", f"Serving GPX gpx_id = '{gpx_id}' to '{current_user.email}', "
                                        f"filename = ({gpx.name}).")
    return send_from_directory(directory=GPX_UPLOAD_FOLDER_ABS,
                               path=os.path.basename(gpx.filename),
                               download_name=download_name)


# -------------------------------------------------------------------------------------------------------------- #
# Download a GPX route (no login link in email)
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_download2', methods=['GET'])
@logout_barred_user
@update_last_seen
def gpx_download2() -> Response | str:
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)
    email = request.args.get('email', None)
    code = request.args.get('code', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"gpx_download2(): Missing gpx_id!")
        EventRepository.log_event("gpx_download2 Fail", f"missing gpx_id!")
        abort(400)
    elif not email:
        app.logger.debug(f"gpx_download2(): Missing email!")
        EventRepository.log_event("gpx_download2 Fail", f"Missing email!")
        abort(400)
    elif not code:
        app.logger.debug(f"gpx_download2(): Missing code!")
        EventRepository.log_event("gpx_download2 Fail", f"Missing code!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = GpxRepository.one_by_id(gpx_id)
    if not gpx:
        app.logger.debug(f"gpx_download2(): Failed to locate GPX with gpx_id = '{gpx_id}' in dB.")
        EventRepository.log_event("gpx_download2 Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        flash("Sorry, we couldn't find that GPX file in the database!")
        return abort(404)

    user: UserModel | None = UserRepository.one_by_email(email)
    if not user:
        app.logger.debug(f"gpx_download2(): Failed to locate user email = '{email}'.")
        EventRepository.log_event("gpx_download2 Fail", f"Failed to locate user email = '{email}'.")
        flash("Sorry, we couldn't find that email address in the database!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check user isn't banned
    # ----------------------------------------------------------- #
    if user.blocked:
        app.logger.debug(f"gpx_download2(): User account blocked, email = '{email}'.")
        EventRepository.log_event("gpx_download2 Fail", f" User account blocked, email = '{email}'.")
        flash("Sorry, but your account has been locked!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Validate download code
    # ----------------------------------------------------------- #
    if code != user.gpx_download_code(gpx.id):
        app.logger.debug(f"gpx_download2(): Passed invalid download code = '{code}'.")
        EventRepository.log_event("gpx_download2 Fail", f"Passed invalid download code = '{code}'.")
        flash("Invalid download code!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check GPX file exists
    # ----------------------------------------------------------- #
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

    if not os.path.exists(filename):
        # Should never get here, but..
        app.logger.debug(f"gpx_download2(): Failed to locate filename = '{filename}', gpx_id = '{gpx_id}'.")
        EventRepository.log_event("gpx_download2 Fail", f"Failed to locate filename = '{filename}', gpx_id = '{gpx_id}'.")
        flash("Sorry, we couldn't find that GPX file on the server!")
        flash("You should probably fire the web developer...")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check GPX is public
    # ----------------------------------------------------------- #
    if not gpx.public:
        owner_name = get_user_name(gpx.email)
        app.logger.debug(f"route_download2(): Private GPX, gpx_id = '{gpx_id}' in dB.")
        EventRepository.log_event("gpx_download2 Fail", f"Private GPX, GPX with gpx_id = '{gpx_id}'.")
        flash(f"Sorry, that GPX file has been marked as Private by '{owner_name}'")
        return abort(404)

    # ----------------------------------------------------------- #
    # Update the GPX file with the correct name (in case it's changed)
    # ----------------------------------------------------------- #
    check_route_name(gpx)

    # ----------------------------------------------------------- #
    # Update count
    # ----------------------------------------------------------- #
    GpxRepository.update_downloads(gpx.id, email)

    # ----------------------------------------------------------- #
    # Send link to download the file
    # ----------------------------------------------------------- #

    # This is the filename the user will see
    download_name = f"ELSR_{gpx.name.replace(' ', '_')}.gpx"

    app.logger.debug(f"gpx_download2d(): Serving GPX gpx_id = '{gpx_id}' ({gpx.name}) to '{user.email}', "
                     f"filename = '{filename}'.")
    EventRepository.log_event("gpx_download2", f"Serving GPX gpx_id = '{gpx_id}' to '{user.email}', "
                                       f"filename = ({gpx.name}).")
    return send_from_directory(directory=GPX_UPLOAD_FOLDER_ABS,
                               path=os.path.basename(gpx.filename),
                               download_name=download_name)


