from flask import render_template, request, flash, abort, redirect, url_for, send_from_directory
from flask_login import login_required, current_user
from werkzeug import exceptions
import os
from datetime import date, datetime, timedelta
from threading import Thread
from ics import Calendar as icsCalendar, Event as icsEvent

# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year

# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, update_last_seen, logout_barred_user, get_user_name
from core.db_classifieds import Classified, CLASSIFIEDS_PHOTO_FOLDER, create_classified_form, MAX_NUM_PHOTOS, SELL, \
                                STATUS_SOLD
from core.dB_events import Event
from core.subs_classified_photos import delete_classifieds_photos, delete_all_classified_photos, add_classified_photos
from core.subs_email_sms import send_message_to_seller


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Show classifieds list
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/classifieds", methods=['GET'])
@update_last_seen
def classifieds():
    # ----------------------------------------------------------- #
    # Did we get passed a classified_id? (Optional)
    # ----------------------------------------------------------- #
    classified_id = request.args.get('classified_id', None)

    # ----------------------------------------------------------- #
    # Validate classified_id
    # ----------------------------------------------------------- #
    if classified_id:
        classified = Classified().find_by_id(classified_id)
        if not classified:
            app.logger.debug(f"classifieds(): Failed to locate classifieds, classified_id = '{classified_id}'.")
            Event().log_event("Classifieds Fail", f"Failed to locate classifieds, classified_id = '{classified_id}'.")
            return abort(404)
    else:
        classified = None

    # ----------------------------------------------------------- #
    # Are we showing one or all?
    # ----------------------------------------------------------- #
    if classified:
        classifieds = [classified]
    else:
        classifieds = Classified().all()

    # ----------------------------------------------------------- #
    # Update image filenames with paths
    # ----------------------------------------------------------- #
    for classified in classifieds:
        classified.images = []
        # Check column isn't None
        if classified.image_filenames:
            # Parse as CSV string
            for image_name in classified.image_filenames.split(','):
                # Strings of single spaces seem to pass for some reason, so exclude them
                if image_name.strip() != "":
                    filename = f"/img/classifieds_photos/{image_name}"
                    # Check file(s) actually exist
                    if os.path.exists(os.path.join(CLASSIFIEDS_PHOTO_FOLDER, os.path.basename(filename))):
                        print(f"Appending '{filename}'")
                        classified.images.append(filename)

    return render_template("classifieds.html", year=current_year, classifieds=classifieds, status_sold=STATUS_SOLD)


# -------------------------------------------------------------------------------------------------------------- #
# Add a sell advert
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/add_sell", methods=['GET', 'POST'])
@update_last_seen
@logout_barred_user
@login_required
def add_sell():
    # ----------------------------------------------------------- #
    # Did we get passed a classified_id? (Optional)
    # ----------------------------------------------------------- #
    classified_id = request.args.get('classified_id', None)

    # ----------------------------------------------------------- #
    # Permissions
    # ----------------------------------------------------------- #
    if not current_user.readwrite():
        # Failed authentication
        app.logger.debug(f"add_sell(): Refusing permission for '{current_user.email}'.")
        Event().log_event("Add Sell Fail", f"Refusing permission for '{current_user.email}'.")
        flash("You do not have permission to add posts to the Classifieds!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Validate classified_id
    # ----------------------------------------------------------- #
    if classified_id:
        classified = Classified().find_by_id(classified_id)
        if not classified:
            app.logger.debug(f"add_sell(): Failed to locate, classified_id = '{classified_id}'.")
            Event().log_event("Edit Sell Fail", f"Failed to locate, classified_id = '{classified_id}'.")
            return abort(404)
    else:
        classified = None

    # ----------------------------------------------------------- #
    # Work out what we're doing (Add / Edit)
    # ----------------------------------------------------------- #
    if request.method == 'GET':
        if classified:
            # ----------------------------------------------------------- #
            # We are editing an existing entry
            # ----------------------------------------------------------- #
            # Sort out num photos (as editing photos in form is tricky)
            num_photos_used = Classified().number_photos(classified_id)
            photos_left = MAX_NUM_PHOTOS - num_photos_used
            # Create form with correct number of outstanding photo upload options
            form = create_classified_form(photos_left)

            # ----------------------------------------------------------- #
            # Add paths to photos as we will display with form
            # ----------------------------------------------------------- #
            classified.images = []
            for image_name in classified.image_filenames.split(','):
                if image_name.strip() != "":
                    filename = f"/img/classifieds_photos/{image_name}"
                    # Check file(s) actually exist
                    if os.path.exists(os.path.join(CLASSIFIEDS_PHOTO_FOLDER, os.path.basename(filename))):
                        classified.images.append(filename)

            # ----------------------------------------------------------- #
            # Need to fill in form from db
            # ----------------------------------------------------------- #
            form.title.data = classified.title
            form.status.data = classified.status
            form.category.data = classified.category
            form.price.data = classified.price
            form.details.data = classified.details

        else:
            # ----------------------------------------------------------- #
            # New classified, so just use blank form
            # ----------------------------------------------------------- #
            num_photos_used = 0
            photos_left = MAX_NUM_PHOTOS - num_photos_used
            form = create_classified_form(photos_left)

    # Are we posting the completed comment form?
    if request.method == 'POST':

        # Need to know number of photos already used up
        if classified:
            num_photos_used = Classified().number_photos(classified_id)
        else:
            num_photos_used = 0

        # Need a form even object
        photos_left = MAX_NUM_PHOTOS - num_photos_used
        form = create_classified_form(photos_left)

        if form.validate_on_submit():
            # ----------------------------------------------------------- #
            # Handle form passing validation
            # ----------------------------------------------------------- #

            # Detect cancel button
            if form.cancel.data:
                return redirect(url_for('classifieds'))

            # ----------------------------------------------------------- #
            # Create new Classified object for the db
            # ----------------------------------------------------------- #
            if classified:
                new_classified = classified
            else:
                new_classified = Classified()

            # Update from form
            new_classified.email = current_user.email
            new_classified.date = date.today().strftime("%d%m%Y")
            new_classified.title = form.title.data
            new_classified.buy_sell = SELL
            new_classified.category = form.category.data
            new_classified.price = form.price.data
            new_classified.details = form.details.data
            new_classified.status = form.status.data

            # ----------------------------------------------------------- #
            # Delete photos
            # ----------------------------------------------------------- #
            print(f"Images before = '{new_classified.image_filenames}'")
            delete_classifieds_photos(new_classified, form)
            print(f"Images after = '{new_classified.image_filenames}'")

            # ----------------------------------------------------------- #
            # Upload photos
            # ----------------------------------------------------------- #
            print(f"Images before = '{new_classified.image_filenames}'")
            add_classified_photos(new_classified, form)
            print(f"Images after = '{new_classified.image_filenames}'")

            # ----------------------------------------------------------- #
            # Add to dB
            # ----------------------------------------------------------- #
            new_classified = Classified().add_classified(new_classified)
            if not new_classified:
                # Should never happen, but...
                app.logger.debug(f"add_sell(): Failed to add classified: '{new_classified}'.")
                Event().log_event("Add Sell Fail", f"Failed to add classified: '{new_classified}'.")
                flash("Sorry, something went wrong.")
                return render_template("classifieds_sell.html", year=current_year, form=form,
                                       num_photos_used=num_photos_used,
                                       classified=classified)

            # Show them their completed post
            return redirect(url_for('classifieds', classified_id=new_classified.id))

        else:
            # ----------------------------------------------------------- #
            # Handle POST (but form validation failed)
            # ----------------------------------------------------------- #
            # Detect cancel button
            if form.cancel.data:
                return redirect(url_for('classifieds'))

            # This traps a post, but where the form verification failed.
            flash("Something was missing, see comments below:")

    return render_template("classifieds_sell.html", year=current_year, form=form, num_photos_used=num_photos_used,
                           classified=classified)


# -------------------------------------------------------------------------------------------------------------- #
# Delete a Classifieds post
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/delete_classified", methods=['POST'])
@update_last_seen
@logout_barred_user
@login_required
def delete_classified():
    # ----------------------------------------------------------- #
    # Did we get passed a classified_id?
    # ----------------------------------------------------------- #
    classified_id = request.args.get('classified_id', None)
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
    # Must have parameters
    # ----------------------------------------------------------- #
    if not classified_id:
        app.logger.debug(f"delete_classified(): Missing classified!")
        Event().log_event("Delete Classified Fail", f"Missing classified!")
        return abort(400)
    if not password:
        app.logger.debug(f"delete_classified(): Missing Password!")
        Event().log_event("Delete Classified Fail", f"Missing Password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate classified_id
    # ----------------------------------------------------------- #
    classified = Classified().find_by_id(classified_id)
    if not classified:
        app.logger.debug(f"delete_classified(): Failed to locate, classified_id = '{classified_id}'.")
        Event().log_event("Delete Classified Fail", f"Failed to locate, classified_id = '{classified_id}.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Must be admin or the current author
    if current_user.email != classified.email \
            and not current_user.admin() or \
            not current_user.readwrite():
        # Failed authentication
        app.logger.debug(f"delete_classified(): Refusing permission for '{current_user.email}' and "
                         f"classified_id = '{classified_id}.")
        Event().log_event("Delete Classified Fail", f"Refusing permission for '{current_user.email}', "
                                                    f"classified_id = '{classified_id}.")
        return abort(403)

    # ----------------------------------------------------------- #
    #  Validate password
    # ----------------------------------------------------------- #
    # Need current user
    user = User().find_user_from_id(current_user.id)

    # Validate against current_user's password
    if not user.validate_password(user, password, user_ip):
        app.logger.debug(
            f"delete_classified(): Delete failed, incorrect password for classified_id = '{classified_id}!")
        Event().log_event("Delete Classified Fail", f"Incorrect password for classified_id = '{classified_id}!")
        flash(f"Incorrect password for user {user.name}!")
        # Go back to socials page
        return redirect(url_for('classifieds'))

    # ----------------------------------------------------------- #
    # Delete Classified photos first
    # ----------------------------------------------------------- #
    delete_all_classified_photos(classified)

    # ----------------------------------------------------------- #
    # Delete Classified
    # ----------------------------------------------------------- #
    if Classified().delete_classified(classified_id):
        app.logger.debug(f"delete_classified(): Deleted social, classified_id = '{classified_id}.")
        Event().log_event("Delete Classified Success", f"Deleted social, classified_id = '{classified_id}.")
        flash("Classified has been deleted.")
    else:
        app.logger.debug(f"delete_classified(): Failed to delete, classified_id = '{classified_id}.")
        Event().log_event("Delete Classified Fail", f"Failed to delete, classified_id = '{classified_id}.")
        flash("Sorry, something went wrong.")

    return redirect(url_for('classifieds'))


# -------------------------------------------------------------------------------------------------------------- #
# Message a seller
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/message_seller", methods=['POST'])
@update_last_seen
@logout_barred_user
@login_required
def message_seller():
    # ----------------------------------------------------------- #
    # Did we get passed a classified_id? (Optional)
    # ----------------------------------------------------------- #
    classified_id = request.args.get('classified_id', None)

    # ----------------------------------------------------------- #
    # Must have classified_id
    # ----------------------------------------------------------- #
    if not classified_id:
        app.logger.debug(f"message_seller(): Missing classified!")
        Event().log_event("message_seller Fail", f"Missing classified!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate classified_id
    # ----------------------------------------------------------- #
    classified = Classified().find_by_id(classified_id)
    if not classified:
        app.logger.debug(f"message_seller(): Failed to locate, classified_id = '{classified_id}'.")
        Event().log_event("Message Seller Fail", f"Failed to locate, classified_id = '{classified_id}.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Read the form
    # ----------------------------------------------------------- #
    user_name = request.form['name'].strip()
    user_email = request.form['email'].strip()
    user_phone = request.form['mobile'].strip()
    user_message = request.form['message'].strip()

    # ----------------------------------------------------------- #
    # Check we have valid data
    # ----------------------------------------------------------- #
    if user_name == "" or \
            user_email == "" or \
            user_message == "":
        flash("You must have a name, email and message!")
        return redirect(url_for('classifieds', classified_id=classified_id))

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    Thread(target=send_message_to_seller, args=(classified, user_name, user_email, user_phone, user_message,)).start()
    flash(f"Email has been sent to user {get_user_name(classified.email)}")

    # ----------------------------------------------------------- #
    # Back to Classified
    # ----------------------------------------------------------- #
    return redirect(url_for('classifieds', classified_id=classified_id))
