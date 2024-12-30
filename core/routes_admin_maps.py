from flask import redirect, url_for, flash, request, abort
from flask_login import current_user
from werkzeug import exceptions


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Import our own Classes
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.user_repository import User
from core.database.repositories.event_repository import EventRepository
from core.subs_google_maps import maps_enabled, set_enable_maps, set_disable_maps, boost_map_limit

from core.decorators.user_decorators import admin_only, update_last_seen, login_required


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Enable maps
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/enable_maps', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def enable_maps():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
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
    #  Need user
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(current_user.id)
    if not user:
        app.logger.debug(f"enable_maps(): Invalid user current_user.id = '{current_user.id}'!")
        EventRepository().log_event("Enable Maps Fail", f"Invalid user current_user.id = '{current_user.id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    #  Validate against current_user's (admins) password
    # ----------------------------------------------------------- #
    if not user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"enable_maps(): Incorrect password for user_id = '{current_user.id}'!")
        EventRepository().log_event("Enable Maps Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for '{current_user.name}'.")
        return redirect(url_for('admin_page', user_id=current_user.id))

    # ----------------------------------------------------------- #
    #  Enable Maps
    # ----------------------------------------------------------- #
    set_enable_maps()

    # Verify
    if maps_enabled():
        app.logger.debug(f"enable_maps(): Enabled Maps, current_user.id = '{current_user.id}'!")
        EventRepository().log_event("Enable Maps Success", f"Enabled Maps, current_user.id = '{current_user.id}'.")
        flash("Maps enabled")
    else:
        app.logger.debug(f"enable_maps(): Failed to enable maps, current_user.id = '{current_user.id}'!")
        EventRepository().log_event("Enable Maps Fail", f"Failed to enable maps, current_user.id = '{current_user.id}'.")
        flash("Sorry, something went wrong")

    # Back to user page
    return redirect(url_for('admin_page', user_id=current_user.id))


# -------------------------------------------------------------------------------------------------------------- #
# Disable maps
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/disable_maps', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def disable_maps():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
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
    #  Need user
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(current_user.id)
    if not user:
        app.logger.debug(f"disable_maps(): Invalid user current_user.id = '{current_user.id}'!")
        EventRepository().log_event("Disable Maps Fail", f"Invalid user current_user.id = '{current_user.id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    #  Validate against current_user's (admins) password
    # ----------------------------------------------------------- #
    if not user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"disable_maps(): Incorrect password for user_id = '{current_user.id}'!")
        EventRepository().log_event("Disable Maps Fail", f"Incorrect password for user_id = '{current_user.id}'!")
        flash(f"Incorrect password for '{current_user.name}'.")
        return redirect(url_for('admin_page', user_id=current_user.id))

    # ----------------------------------------------------------- #
    #  Disable Maps
    # ----------------------------------------------------------- #
    set_disable_maps()

    # Verify
    if not maps_enabled():
        app.logger.debug(f"disable_maps(): Disabled Maps, current_user.id = '{current_user.id}'!")
        EventRepository().log_event("Disable Maps Success", f"Disabled Maps, current_user.id = '{current_user.id}'.")
        flash("Maps disabled")
    else:
        app.logger.debug(f"disable_maps(): Failed to disable maps, current_user.id = '{current_user.id}'!")
        EventRepository().log_event("Disable Maps Fail", f"Failed to disable maps, current_user.id = '{current_user.id}'.")
        flash("Sorry, something went wrong")

    # Back to user page
    return redirect(url_for('admin_page', user_id=current_user.id))


# -------------------------------------------------------------------------------------------------------------- #
# Boost map limit for the day
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/boost_maps', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def boost_maps():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
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
    #  Need user
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(current_user.id)
    if not user:
        app.logger.debug(f"boost_maps(): Invalid user current_user.id = '{current_user.id}'!")
        EventRepository().log_event("Boost Maps Fail", f"Invalid user current_user.id = '{current_user.id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    #  Validate against current_user's (admins) password
    # ----------------------------------------------------------- #
    if not user.validate_password(current_user, password, user_ip):
        app.logger.debug(f"boost_maps(): Incorrect password for '{current_user.email}'!")
        EventRepository().log_event("Boost Maps Fail", f"Incorrect password for '{current_user.email}'!")
        flash(f"Incorrect password for '{current_user.name}'.")
        return redirect(url_for('admin_page', user_id=current_user.id))

    # ----------------------------------------------------------- #
    #  Boost Maps
    # ----------------------------------------------------------- #
    boost_map_limit()

    # Feedback
    app.logger.debug(f"boost_maps(): Map boost applied by '{current_user.email}'.")
    EventRepository().log_event("Boost Maps Success", f"Map boost applied by '{current_user.email}'.")
    flash("Maps boost has been applied")

    # Back to user page
    return redirect(url_for('admin_page', user_id=current_user.id))

