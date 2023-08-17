from flask import render_template, redirect, url_for, flash, request, abort, send_from_directory
from flask_login import login_required, current_user
from flask_googlemaps import Map
from werkzeug import exceptions
import os
from threading import Thread


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS, dynamic_map_size, dynamic_graph_size, \
                 current_year, delete_file_if_exists, is_mobile, GOOGLE_MAPS_API_KEY


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_gpx import Gpx, UploadGPXForm
from core.db_users import User, update_last_seen, logout_barred_user
from core.dB_cafes import Cafe
from core.dB_events import Event
from core.subs_gpx import allowed_file, cut_start_gpx, cut_end_gpx, check_route_name, markers_for_gpx,\
                          markers_for_cafes, start_and_end_maps, get_elevation_data, get_cafe_heights,\
                          strip_excess_info_from_gpx, check_new_gpx_with_all_cafes, polyline_json,\
                          markers_for_cafes_native, start_and_end_maps_native_gm


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
def gpx_list():

    # Grab all our routes
    gpxes = Gpx().all_gpxes()

    # Double check we have all the files present
    missing_files = []

    for gpx in gpxes:
        # Absolute path name
        filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))

        # Check the file is actually there, before we try and parse it etc
        if not os.path.exists(filename):
            missing_files.append(gpx.id)

    # Need different path for Admin
    if not current_user.is_authenticated:
        admin = False
    elif current_user.admin():
        admin = True
    else:
        admin = False

    if admin:
        for missing in missing_files:
            flash(f"We are missing the GPX file for route {missing}!")

    # Render in gpx_list template
    return render_template("gpx_list.html", year=current_year,  gpxes=gpxes, mobile=is_mobile(),
                           missing_files=missing_files)


# -------------------------------------------------------------------------------------------------------------- #
# Display a single GPX file
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/route/<int:gpx_id>', methods=['GET'])
@update_last_seen
def gpx_details(gpx_id):

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"gpx_details(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("One GPX Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Route must be public
    # Tortuous logic as a non logged-in user doesn't have any of our custom attributes eg email etc
    if not gpx.public() and \
       not current_user.is_authenticated:
        app.logger.debug(f"gpx_details(): Refusing permission for non logged in user and hidden route '{gpx_id}'.")
        Event().log_event("One GPX Fail", f"Refusing permission for non logged in user and hidden route '{gpx_id}'.")
        return abort(403)

    elif not gpx.public() and \
         current_user.email != gpx.email and \
         not current_user.admin():
        app.logger.debug(f"gpx_details(): Refusing permission for user '{current_user.email}' to see "
                         f"hidden GPX route '{gpx.id}'!")
        Event().log_event("One GPX Fail", f"Refusing permission for user {current_user.email} to see "
                                          f"hidden GPX route, gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Get info for webpage
    # ----------------------------------------------------------- #
    author = User().find_user_from_email(gpx.email).name
    cafe_list = Cafe().cafe_list(gpx.cafes_passed)

    # ----------------------------------------------------------- #
    # Double check GPX file actually exists
    # ----------------------------------------------------------- #

    # This is the absolute path to the file
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))

    # Check the file is actually there, before we try and parse it etc
    if not os.path.exists(filename):
        # Should never happen, but may as well handle it cleanly

        # Need different path for Admin
        if not current_user.is_authenticated:
            admin = False
        elif current_user.admin():
            admin = True
        else:
            admin = False

        if admin:
            # Admin needs to be able to rectify the situation
            app.logger.debug(f"gpx_details(): Can't find '{filename}'!")
            Event().log_event("One GPX Fail", f"Can't find '{filename}'!")
            flash("Sorry, we seem to have lost that GPX file!")
        else:
            # Non admin just gets a Dear John...
            app.logger.debug(f"gpx_details(): Can't find '{filename}'!")
            Event().log_event("One GPX Fail", f"Can't find '{filename}'!")
            flash("Sorry, we seem to have lost that GPX file!")
            flash("Someone should probably fire the web developer...")
            return abort(404)

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
        cafe_elevation_data = get_cafe_heights(cafe_list, elevation_data)
    else:
        elevation_data = []
        cafe_elevation_data = []

    # ----------------------------------------------------------- #
    # Flag if hidden
    # ----------------------------------------------------------- #
    if not gpx.public():
        flash("This route is not public yet!")

    # Render in main index template
    return render_template("gpx_details.html", gpx=gpx, year=current_year, cafe_markers=cafe_markers,
                           author=author, cafe_list=cafe_list, elevation_data=elevation_data,
                           cafe_elevation_data=cafe_elevation_data, GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY,
                           polyline=polyline['polyline'], midlat=polyline['midlat'], midlon=polyline['midlon'])


# -------------------------------------------------------------------------------------------------------------- #
# Make a route public
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/publish_route', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def publish_route():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"publish_route(): Missing gpx_id!")
        Event().log_event("Publish GPX Fail", f"Missing gpx_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"publish_route(): Failed to locate GPX with gpx_id = '{gpx_id}'!")
        Event().log_event("Publish GPX Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
            or not current_user.can_post_gpx():
        # Failed authentication
        app.logger.debug(f"publish_route(): Refusing permission for '{current_user.email}' to and route '{gpx.id}'!")
        Event().log_event("Publish GPX Fail", f"Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Publish route
    # ----------------------------------------------------------- #
    if Gpx().publish(gpx_id):
        app.logger.debug(f"publish_route(): Route published gpx.id = '{gpx.id}'.")
        Event().log_event("Publish GPX Success", f"Route published with gpx_id = '{gpx_id}'.")
        flash("Route has been published!")
    else:
        app.logger.debug(f"publish_route(): Failed to publish route gpx.id = '{gpx.id}'.")
        Event().log_event("Publish GPX Fail", f"Failed to publish, gpx_id = '{gpx_id}'.")
        flash("Sorry, something went wrong!")

    # ----------------------------------------------------------- #
    # Clear existing nearby cafe list
    # ----------------------------------------------------------- #
    if not Gpx().clear_cafe_list(gpx_id):
        app.logger.debug(f"publish_route(): Failed clear cafe list gpx.id = '{gpx.id}'.")
        Event().log_event("Publish GPX Fail", f"Failed clear cafe list, gpx_id = '{gpx_id}'.")
        flash("Sorry, something went wrong!")
        return redirect(url_for('edit_route', gpx_id=gpx_id))

    # ----------------------------------------------------------- #
    # Add new existing nearby cafe list
    # ----------------------------------------------------------- #
    flash("Nearby cafe list is being updated.")
    Thread(target=check_new_gpx_with_all_cafes, args=(gpx_id,)).start()

    # Redirect back to the details page as the route is now public, ie any editing is over
    return redirect(url_for('gpx_details', gpx_id=gpx_id))


# -------------------------------------------------------------------------------------------------------------- #
# Make a route private
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/hide_route', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def hide_route():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"hide_route(): Missing gpx_id!")
        Event().log_event("Hide GPX Fail", f"Missing gpx_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"hide_route(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("Hide GPX Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
            or not current_user.can_post_gpx():
        # Failed authentication
        app.logger.debug(f"hide_route(): Refusing permission for {current_user.email} to "
                         f"and route gpx_id = '{gpx_id}'.")
        Event().log_event("Hide GPX Fail", f"Refusing permission for {current_user.email} to "
                                           f"and route gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Hide route
    # ----------------------------------------------------------- #
    if Gpx().hide(gpx_id):
        app.logger.debug(f"hide_route(): Route hidden gpx_id = '{gpx_id}'.")
        Event().log_event("Hide GPX Success", f"Route hidden gpx_id = '{gpx_id}'.")
        flash("Route has been hidden.")
    else:
        # Should never happen, but...
        app.logger.debug(f"hide_route(): Gpx().hide() failed for gpx_id = '{gpx_id}'.")
        Event().log_event("Hide GPX Fail", f"SGpx().hide() failed for gpx_id = '{gpx_id}'.")
        flash("Sorry, something went wrong!")

    # Redirect back to the edit page as that's probably what they want to do next
    return redirect(url_for('edit_route', gpx_id=gpx_id))


# -------------------------------------------------------------------------------------------------------------- #
# Add a GPX ride to the dB
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/new_route', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def new_route():
    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if not current_user.can_post_gpx():
        Event().log_event("New GPX Fail", f"Refusing permission for user {current_user.email} to upload GPX route!")
        app.logger.debug(f"new_route(): Refusing permission for user {current_user.email} to upload GPX route!")
        return abort(403)

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
            Event().log_event(f"New GPX Fail", f"Failed to find 'filename' in request.files!")
            flash("Couldn't find the file.")
            return render_template("gpx_add.html", year=current_year, form=form)

        else:
            # Get the filename
            file = request.files['filename']
            app.logger.debug(f"new_route(): About to upload '{file}'.")

            # If the user does not select a file, the browser submits an
            # empty file without a filename.
            if file.filename == '':
                app.logger.debug(f"new_route(): No selected file!")
                Event().log_event(f"New GPX Fail", f"No selected file!")
                flash('No selected file')
                return redirect(request.url)

            if not file or \
               not allowed_file(file.filename):
                app.logger.debug(f"new_route(): Invalid file '{file.filename}'!")
                Event().log_event(f"New GPX Fail", f"Invalid file '{file.filename}'!")
                flash("That's not a GPX file!")
                return redirect(request.url)

            # Create a new GPX object
            # We do this first as we need the id in order to create
            # the filename for the GPX file when we upload it
            gpx = Gpx()
            gpx.name = form.name.data
            gpx.email = current_user.email
            gpx.cafes_passed = "[]"
            gpx.ascent_m = 0
            gpx.length_km = 0
            gpx.filename = "tmp"

            # Add to the dB
            new_id = gpx.add_gpx(gpx)
            if new_id:
                # Success, added GPX to dB
                # Have to re-get the GPX as it's changed since we created it
                gpx = Gpx().one_gpx(new_id)
                app.logger.debug(f"new_route(): GPX added to dB, id = '{gpx.id}'.")
                Event().log_event(f"New GPX Success", f" GPX added to dB, gpx.id = '{gpx.id}'.")
            else:
                # Failed to create new dB entry
                app.logger.debug(f"new_route(): Failed to add gpx to the dB!")
                Event().log_event(f"New GPX Fail", f"Failed to add gpx to the dB!")
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form)

            # This is where we will store it
            filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, f"gpx_{gpx.id}.gpx")
            app.logger.debug(f"new_route(): Filename will be = '{filename}'.")

            # Make sure this doesn't already exist
            if not delete_file_if_exists(filename):
                # Failed to delete existing file (func will generate error trace)
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form)

            # Upload the GPX file
            try:
                file.save(filename)
            except Exception as e:
                app.logger.debug(f"new_route(): Failed to upload/save '{filename}', error code was {e.args}.")
                Event().log_event(f"New GPX Fail", f"Failed to upload/save '{filename}', error code was {e.args}.")
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form)

            # Update gpx object with filename
            if not Gpx().update_filename(gpx.id, filename):
                app.logger.debug(f"new_route(): Failed to update filename in the dB for gpx_id='{gpx.id}'.")
                Event().log_event(f"New GPX Fail", f"Failed to update filename in the dB for gpx_id='{gpx.id}'.")
                flash("Sorry, something went wrong!")
                return render_template("gpx_add.html", year=current_year, form=form)

            # Strip all excess data from the file
            flash("Any HR or Power data has been removed.")
            strip_excess_info_from_gpx(filename, gpx.id, f"ELSR: {gpx.name}")

            # Forward to edit route as that's the next step
            app.logger.debug(f"new_route(): New GPX added, gpx_id = '{gpx.id}', ({gpx.name}).")
            Event().log_event(f"New GPX Success", f"New GPX added, gpx_id = '{gpx.id}', ({gpx.name}).")
            return redirect(url_for('edit_route', gpx_id=gpx.id))

    elif request.method == 'POST':

        # ----------------------------------------------------------- #
        #   POST - form validation failed
        # ----------------------------------------------------------- #
        flash("Form not filled in properly, see below!")

        return render_template("gpx_add.html", year=current_year, form=form)

    # ----------------------------------------------------------- #
    #   GET - render form etc
    # ----------------------------------------------------------- #

    return render_template("gpx_add.html", year=current_year, form=form)


# -------------------------------------------------------------------------------------------------------------- #
# Allow the user to edit a GPX file
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/edit_route', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def edit_route():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"edit_route(): Missing gpx_id!")
        Event().log_event("Edit GPX Fail", f"Missing gpx_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"edit_route(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("Edit GPX Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check the file exist
    # ----------------------------------------------------------- #
    # This is the absolute path to the file
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))

    # Check the file is actually there, before we try and parse it etc
    if not os.path.exists(filename):
        app.logger.debug(f"edit_route(): Failed to locate GPX file for gpx_id = '{gpx_id}'.")
        Event().log_event("Edit GPX Fail", f"Failed to locate GPX file for gpx_id = '{gpx_id}'.")
        flash(f"We seem to have lost the GPX file for route #{gpx_id} ({gpx.name})!")
        return redirect(url_for('gpx_list'))

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
       or not current_user.can_post_gpx():
        # Failed authentication
        app.logger.debug(f"edit_route(): Refusing permission for '{current_user.email}' and route '{gpx.id}'.")
        Event().log_event("Edit GPX Fail", f"Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    #   Generate Start and Finish maps
    # ----------------------------------------------------------- #
    maps = start_and_end_maps_native_gm(gpx.filename, gpx_id)

    return render_template("gpx_edit.html", year=current_year, gpx=gpx, GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY,
                           start_markers=maps[0], start_map_coords=maps[1],
                           end_markers=maps[2], end_map_coords=maps[3])


# -------------------------------------------------------------------------------------------------------------- #
# Crop the start of a GPX  (called from within the google map via hyperlinked icons)
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_cut_start', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def gpx_cut_start():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)
    index = request.args.get('index', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"gpx_cut_start(): Missing gpx_id!")
        Event().log_event("Cut Start Fail", f"Missing gpx_id!")
        return abort(400)
    elif not index:
        app.logger.debug(f"gpx_cut_start(): Missing index!")
        Event().log_event("Cut Start Fail", f"Missing index!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)
    index = int(index)

    if not gpx:
        app.logger.debug(f"gpx_cut_start(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Cut Start Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ToDo: Need to check index is valid

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
            or not current_user.can_post_gpx():
        # Failed authentication
        app.logger.debug(f"gpx_cut_start(): Refusing permission for '{current_user.email}' and route '{gpx_id}'.")
        Event().log_event("GPX Cut Start Fail", f"Refusing permission for {current_user.email}, gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Cut start of route
    # ----------------------------------------------------------- #
    cut_start_gpx(gpx.filename, index)

    # ----------------------------------------------------------- #
    # Update GPX for cafes
    # ----------------------------------------------------------- #
    if Gpx().clear_cafe_list(gpx_id):
        # Go ahead and update the list
        flash("Nearby cafe list is being been updated.")
        Thread(target=check_new_gpx_with_all_cafes, args=(gpx_id,)).start()

    else:
        # Should never happen, but...
        app.logger.debug(f"gpx_cut_start(): Failed to clear cafe list, gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Cut Start Fail", f"Failed to clear cafe list, gpx_id = '{gpx_id}'.")
        flash("Sorry, something went wrong!")

    # Back to the edit page
    return redirect(url_for('edit_route', gpx_id=gpx_id))


# -------------------------------------------------------------------------------------------------------------- #
# Crop the start of a GPX (called from within the google map via hyperlinked icons)
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_cut_end', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def gpx_cut_end():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)
    index = request.args.get('index', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not gpx_id:
        app.logger.debug(f"gpx_cut_end(): Missing gpx_id!")
        Event().log_event("Cut End Fail", f"Missing gpx_id!")
        return abort(400)
    elif not index:
        app.logger.debug(f"gpx_cut_end(): Missing index!")
        Event().log_event("Cut End Fail", f"Missing index!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)
    index = int(index)

    if not gpx:
        app.logger.debug(f"gpx_cut_end(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Cut End Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ToDo: Need to check index is valid

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
            or not current_user.can_post_gpx():
        # Failed authentication
        app.logger.debug(f"gpx_cut_end(): Refusing permission for '{current_user.email}' and route '{gpx_id}'!")
        Event().log_event("GPX Cut End Fail", f"Refusing permission for {current_user.email}, gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Cut end of route
    # ----------------------------------------------------------- #
    cut_end_gpx(gpx.filename, index)

    # ----------------------------------------------------------- #
    # Update GPX for cafes
    # ----------------------------------------------------------- #
    if Gpx().clear_cafe_list(gpx_id):
        # Go ahead and update the list
        flash("Nearby cafe list is being updated...")
        Thread(target=check_new_gpx_with_all_cafes, args=(gpx_id,)).start()
    else:
        # Should never get here, but..
        app.logger.debug(f"gpx_cut_end(): Gpx().clear_cafe_list() failed for gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Cut End Fail", f"Gpx().clear_cafe_list() failed for gpx_id = '{gpx_id}'.")
        flash("Sorry, something went wrong!")

    # Back to the edit page
    return redirect(url_for('edit_route', gpx_id=gpx_id))


# -------------------------------------------------------------------------------------------------------------- #
# Delete a GPX route
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_delete', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def route_delete():
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
        Event().log_event("GPX Delete Fail", f"Missing gpx_id!")
        return abort(400)
    elif not password:
        app.logger.debug(f"route_delete(): Missing Password!")
        Event().log_event("GPX Delete Fail", f"Missing Password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"route_delete(): Failed to locate GPX with gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Delete Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Must be admin or the current author
    # 2. Must not be barred (NB Admins cannot be barred)
    if (current_user.email != gpx.email
        and not current_user.admin()) \
            or not current_user.can_post_gpx():
        app.logger.debug(f"route_delete(): Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Delete Fail", f"Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    #  Validate password
    # ----------------------------------------------------------- #
    # Need current user
    user = User().find_user_from_id(current_user.id)

    # Validate against current_user's password
    if not user.validate_password(user, password, user_ip):
        app.logger.debug(f"route_delete(): Delete failed, incorrect password for user_id = '{user.id}'!")
        Event().log_event("GPX Delete Fail", f"Incorrect password for user_id = '{user.id}'!")
        flash(f"Incorrect password for user {user.name}!")
        # Go back to route detail page
        return redirect(url_for('gpx_details', gpx_id=gpx_id))

    # ----------------------------------------------------------- #
    # Delete #1: Remove from dB
    # ----------------------------------------------------------- #
    if Gpx().delete_gpx(gpx.id):
        app.logger.debug(f"route_delete(): Success, gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Delete Success", f"Successfully deleted GPX from dB, gpx_id = {gpx_id}!")
        flash("Route was deleted!")
    else:
        # Should never get here, but..
        app.logger.debug(f"route_delete(): Gpx().delete_gpx(gpx.id) failed for gpx.id = '{gpx.id}'.")
        Event().log_event("GPX Delete Fail", f"Gpx().delete_gpx(gpx.id) failed for gpx.id = '{gpx.id}'.")
        flash("Sorry, something went wrong!")
        # Back to GPX list page
        return redirect(url_for('gpx_list'))

    # ----------------------------------------------------------- #
    # Delete #2: Remove GPX file itself
    # ----------------------------------------------------------- #
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))
    try:
        os.remove(filename)
        app.logger.debug(f"route_delete(): File '{filename}' deleted from directory.")
    except Exception as e:
        app.logger.debug(f"route_delete(): Failed to delete GPX file '{filename}', error code was '{e.args}'.")
        Event().log_event("GPX Delete Fail", f"Failed to delete GPX file '{filename}', "
                                             f"error code was {e.args}, gpx_id = {gpx_id}!")

    # Back to GPX list page
    return redirect(url_for('gpx_list'))


# -------------------------------------------------------------------------------------------------------------- #
# Download a GPX route
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/gpx_download/<int:gpx_id>', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def route_download(gpx_id):

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    gpx = Gpx().one_gpx(gpx_id)

    if not gpx:
        app.logger.debug(f"route_download(): Failed to locate GPX with gpx_id = '{gpx_id}' in dB.")
        Event().log_event("GPX Download Fail", f"Failed to locate GPX with gpx_id = '{gpx_id}'.")
        flash("Sorry, we couldn't find that GPX file in the database!")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check GPX file exists
    # ----------------------------------------------------------- #
    filename = os.path.join(os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename)))

    if not os.path.exists(filename):
        # Should never get here, but..
        app.logger.debug(f"route_download(): Failed to locate filename = '{filename}', gpx_id = '{gpx_id}'.")
        Event().log_event("GPX Download Fail", f"Failed to locate filename = '{filename}', gpx_id = '{gpx_id}'.")
        flash("Sorry, we couldn't find that GPX file on the server!")
        flash("You should probably fire the web developer...")
        return abort(404)

    # ----------------------------------------------------------- #
    # Update the GPX file with the correct name (in case it's changed)
    # ----------------------------------------------------------- #

    check_route_name(gpx)

    # ----------------------------------------------------------- #
    # Send link to download the file
    # ----------------------------------------------------------- #

    download_name = f"ELSR_{gpx.name.replace(' ','_')}.gpx"

    app.logger.debug(f"route_download(): Serving GPX gpx_id = '{gpx_id}' ({gpx.name}), filename = '{filename}'.")
    Event().log_event("GPX Downloaded", f"Serving GPX gpx_id = '{gpx_id}' ({gpx.name}).")
    return send_from_directory(directory=GPX_UPLOAD_FOLDER_ABS,
                               path=os.path.basename(gpx.filename),
                               download_name=download_name)

