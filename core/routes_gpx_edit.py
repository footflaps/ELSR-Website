from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
import os
from threading import Thread

# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, GPX_UPLOAD_FOLDER_ABS, current_year, live_site

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_gpx import Gpx, create_rename_gpx_form
from core.db_users import User, update_last_seen, logout_barred_user
from core.dB_events import Event
from core.subs_gpx import check_new_gpx_with_all_cafes
from core.subs_google_maps import start_and_end_maps_native_gm, MAP_BOUNDS, google_maps_api_key, count_map_loads
from core.subs_gpx_edit import cut_start_gpx, cut_end_gpx


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Allow the user to edit a GPX file
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/edit_route', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def edit_route():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    gpx_id = request.args.get('gpx_id', None)
    # return_path is optional
    return_path = request.args.get('return_path', None)

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
    filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))

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
            or not current_user.readwrite():
        # Failed authentication
        app.logger.debug(f"edit_route(): Refusing permission for '{current_user.email}' and route '{gpx.id}'.")
        Event().log_event("Edit GPX Fail", f"Refusing permission for '{current_user.email}', gpx_id = '{gpx_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    #   Form to help them rename the route
    # ----------------------------------------------------------- #
    form = create_rename_gpx_form(current_user.admin())

    if form.validate_on_submit():
        # ----------------------------------------------------------- #
        # Handle form passing validation
        # ----------------------------------------------------------- #

        # Get new GPX name from the form
        new_name = form.name.data
        new_type = form.type.data
        new_details = form.details.data

        # Admin can change ownership
        if current_user.admin():
            # Get new owner
            new_user = User().find_user_from_id(form.owner.data.split('(')[1].split(')')[0])
        else:
            # Make sure we have new_user defined if not admin user
            new_user = User().find_user_from_email(gpx.email)

        # Do we need to update anything?
        if new_name != gpx.name \
                or new_user.email != gpx.email \
                or new_type != gpx.type \
                or new_details != gpx.details:

            # Update GPX
            gpx.name = new_name
            gpx.type = new_type
            gpx.email = new_user.email
            gpx.details = new_details

            # Write to db
            if Gpx().add_gpx(gpx):
                app.logger.debug(f"edit_route(): Successfully updated GPX '{gpx.id}'.")
                Event().log_event("Edit GPX Success", f"Successfully updated GPX '{gpx_id}'.")
                flash("Details have been updated!")
            else:
                # Should never get here, but...
                app.logger.debug(f"edit_route(): Failed to update GPX '{gpx.id}'.")
                Event().log_event("Edit GPX Fail", f"Failed to update GPX '{gpx_id}'.")
                flash("Sorry, something went wrong!")

        else:
            flash("Nothing was changed!")

    elif request.method == 'POST':
        # ----------------------------------------------------------- #
        # Handle POST
        # ----------------------------------------------------------- #

        # Only get here is form validation failed..
        flash("Something was missing in the form!")

    # ----------------------------------------------------------- #
    #   Generate Start and Finish maps
    # ----------------------------------------------------------- #
    maps = start_and_end_maps_native_gm(gpx.filename, gpx_id, return_path)

    if request.method == 'GET':
        # Pre-fill form with existing name
        form.name.data = gpx.name
        form.type.data = gpx.type
        form.details.data = gpx.details
        # And existing owner
        if current_user.admin():
            user = User().find_user_from_email(gpx.email)
            form.owner.data = f"{user.name} ({user.id})"

    # Keep count of Google Map Loads
    count_map_loads(1)

    # Render the page
    return render_template("gpx_edit.html", year=current_year, gpx=gpx, GOOGLE_MAPS_API_KEY=google_maps_api_key(),
                           MAP_BOUNDS=MAP_BOUNDS, start_markers=maps[0], start_map_coords=maps[1],
                           end_markers=maps[2], end_map_coords=maps[3], return_path=return_path, form=form,
                           live_site=live_site())


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
    # return_path is optional
    return_path = request.args.get('return_path', None)

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
            or not current_user.readwrite():
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
    return redirect(url_for('edit_route', gpx_id=gpx_id, return_path=return_path))


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
    # return_path is optional
    return_path = request.args.get('return_path', None)

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
            or not current_user.readwrite():
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
    return redirect(url_for('edit_route', gpx_id=gpx_id, return_path=return_path))


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
    # return_path is optional
    return_path = request.args.get('return_path', None)

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
            or not current_user.readwrite():
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
        return redirect(url_for('edit_route', gpx_id=gpx_id, return_path=return_path))

    # ----------------------------------------------------------- #
    # Add new existing nearby cafe list
    # ----------------------------------------------------------- #
    flash("Nearby cafe list is being updated.")
    Thread(target=check_new_gpx_with_all_cafes, args=(gpx_id,)).start()

    # Decide where to go next...
    if return_path and \
            return_path != "None":
        # Go back to specific page
        return redirect(return_path)
    else:
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
    # return_path is optional
    return_path = request.args.get('return_path', None)

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
            or not current_user.readwrite():
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
    return redirect(url_for('edit_route', gpx_id=gpx_id, return_path=return_path))
