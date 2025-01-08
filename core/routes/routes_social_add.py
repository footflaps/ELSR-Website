from flask import render_template, url_for, request, flash, redirect, abort, Response
from flask_login import current_user
from werkzeug import exceptions
from datetime import datetime
from threading import Thread


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.social_repository import SocialModel, SocialRepository, SOCIAL_FORM_PRIVATE, SOCIAL_DB_PRIVATE, \
                                                         SOCIAL_FORM_PUBLIC, SOCIAL_DB_PUBLIC, SIGN_UP_YES, SIGN_UP_NO
from core.forms.social_forms import create_social_form
from core.database.repositories.event_repository import EventRepository
from core.database.repositories.user_repository import UserModel, UserRepository
from core.subs_email import send_social_notification_emails

from core.decorators.user_decorators import update_last_seen, logout_barred_user, login_required, rw_required


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Add a social event
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/add_social', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def route_add_social() -> Response | str:
    # ----------------------------------------------------------- #
    # Did we get passed a social_id? (Optional)
    # ----------------------------------------------------------- #
    social_id: str = request.args.get('social_id', None)

    # ----------------------------------------------------------- #
    # Validate social_id
    # ----------------------------------------------------------- #
    if social_id:
        # Check id is an int!
        try:
            int(social_id)
        except ValueError:
            flash(f"Invalid social id '{social_id}', was expecting integer!")
            return abort(404)

        # Look up the social by id
        social = SocialRepository().one_by_id(id=int(social_id))

        # Handle failure...
        if not social:
            app.logger.debug(f"add_social(): Failed to locate social, social_id = '{social_id}'.")
            EventRepository().log_event("Add Social Fail", f"Failed to locate social, social_id = '{social_id}'.")
            return abort(404)

    else:
        social: SocialModel | None = None

    # ----------------------------------------------------------- #
    # Need a form
    # ----------------------------------------------------------- #
    form = create_social_form(current_user.admin)

    if request.method == 'GET':
        if social:
            # Try and get owner from email address in the db
            owner: UserModel | None = UserRepository().find_user_from_email(social.email)
            if not owner:
                # Should never happen but....
                app.logger.debug(f"add_social(): Failed to locate owner, "
                                 f"social_id = '{social_id}', social.email = '{social.email}'.")
                EventRepository().log_event("Edit Social Fail", f"Failed to locate owner, "
                                                      f"social_id = '{social_id}', social.email = '{social.email}'.")
                flash("Failed to locate owner, so defaulting to current_user")
                # Default to current user
                owner = current_user

            # We are editing an existing event, so pre-fill details
            form.date.data = datetime.strptime(social.date.strip(), '%d%m%Y')
            form.start_time.data = datetime.strptime(f"{social.date} {social.start_time}", '%d%m%Y %H%M').time()
            form.organiser.data = social.organiser
            form.destination.data = social.destination
            form.details.data = social.details
            if social.privacy == SOCIAL_DB_PRIVATE:
                form.destination_hidden.data = SOCIAL_FORM_PRIVATE
            else:
                form.destination_hidden.data = SOCIAL_FORM_PUBLIC
            if social.sign_up == "True":
                form.sign_up.data = SIGN_UP_YES
            else:
                form.sign_up.data = SIGN_UP_NO

            # Admin owner option
            if current_user.admin:
                form.owner.data = owner.combo_str

        else:
            # New form, so just assume organiser is current user
            form.organiser.data = current_user.name
            if current_user.admin:
                form.owner.data = current_user.combo_str

            # Add some guidance
            form.details.data = "<p>If you set the Social type to <strong>Public</strong>:</p>" \
                                "<ul><li>Destination and Details are hidden for anyone not logged in.</li>" \
                                "<li>But, visible to anyone who has registered (ie anyone who can be bothered to give " \
                                "the site an email address).</li></ul>" \
                                "<p>However, the Admins maintain a subset of members (same as WA group) and only " \
                                "these people can see the Destination and Details of <strong>Private</strong> events. " \
                                "So, <strong>Public</strong> = social down the pub, but BBQ at your house should be " \
                                "made <strong>Private</strong>!</p>"

    elif form.validate_on_submit():
        # ----------------------------------------------------------- #
        # Handle form passing validation
        # ----------------------------------------------------------- #

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('calendar'))  # type: ignore

        # ----------------------------------------------------------- #
        # We can now create / update the social object
        # ----------------------------------------------------------- #
        if social:
            # Updating an existing social
            new_social: SocialModel = social
        else:
            # New social
            new_social = SocialModel()

        # Get owner
        if current_user.admin:
            owner = UserRepository().user_from_combo_string(form.owner.data)
            if not owner:
                # Should never happen but....
                app.logger.debug(f"add_social(): Failed to locate owner, "
                                 f"social_id = '{social_id}', social.email = '{social.email}'.")
                EventRepository().log_event("Edit Social Fail", f"Failed to locate owner, "
                                                      f"social_id = '{social_id}', social.email = '{social.email}'.")
                flash("Failed to locate owner, so defaulting to current_user")
                # Default to current user
                owner = current_user
        else:
            owner = current_user

        new_social.organiser = form.organiser.data
        new_social.email = owner.email
        # Convert form date format '2023-06-23' to preferred format '23062023'
        new_social.date = form.date.data.strftime("%d%m%Y")
        new_social.converted_date = form.date.data
        new_social.start_time = form.start_time.data.strftime("%H%M")
        new_social.destination = form.destination.data
        new_social.details = form.details.data
        # Handle public private
        if form.destination_hidden.data == SOCIAL_FORM_PUBLIC:
            new_social.privacy = SOCIAL_DB_PUBLIC
        else:
            new_social.privacy = SOCIAL_DB_PRIVATE
        # Handle sign-ups
        if form.sign_up.data == SIGN_UP_YES:
            new_social.sign_up = "True"
        else:
            new_social.sign_up = "False"

        # ----------------------------------------------------------- #
        # Add to the db
        # ----------------------------------------------------------- #
        new_social = SocialRepository().add_social(new_social)
        if new_social:
            # Success
            app.logger.debug(f"add_social(): Successfully added new social.")
            EventRepository().log_event("Add social Pass", f"Successfully added new social.")
            if social:
                flash("Social updated!")
            else:
                flash("Social added to Calendar!")
                Thread(target=send_social_notification_emails, args=(new_social,)).start()
            # Back to socials page showing the new social
            return redirect(url_for('display_socials', date=new_social.date))  # type: ignore

        else:
            # Should never happen, but...
            # NB new_social is None
            app.logger.debug(f"add_social(): Failed to add social for '{current_user.email}'.")
            EventRepository().log_event("Add Social Fail", f"Failed to add social for '{current_user.email}'.")
            flash("Sorry, something went wrong.")
            return render_template("calendar_add_social.html", year=current_year, form=form, social=social,
                                   live_site=live_site())

    elif request.method == 'POST':
        # ----------------------------------------------------------- #
        # Handle form failing validation
        # ----------------------------------------------------------- #

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('calendar'))  # type: ignore

        # This traps a post, but where the form verification failed.
        flash("Something was missing, see comments below:")
        return render_template("calendar_add_social.html", year=current_year, form=form, social=social,
                               live_site=live_site())

    return render_template("calendar_add_social.html", year=current_year, form=form, social=social,
                           live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Add a social event
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/delete_social', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
@rw_required
def delete_social() -> Response | str:
    # ----------------------------------------------------------- #
    # Did we get passed a social_id?
    # ----------------------------------------------------------- #
    social_id = request.args.get('social_id', None)
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
    if not social_id:
        app.logger.debug(f"delete_social(): Missing social_id!")
        EventRepository().log_event("Delete social Fail", f"Missing social_id!")
        return abort(400)
    if not password:
        app.logger.debug(f"delete_social(): Missing Password!")
        EventRepository().log_event("Delete social Fail", f"Missing Password!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate social_id
    # ----------------------------------------------------------- #
    social = SocialRepository().one_by_id(social_id)
    if not social:
        app.logger.debug(f"delete_social(): Failed to locate social, social_id = '{social_id}'.")
        EventRepository().log_event("Delete Social Fail", f"Failed to locate social, social_id = '{social_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access to Admin and Author
    # ----------------------------------------------------------- #
    # Must be admin or the current author
    if current_user.email != social.email \
            and not current_user.admin:
        # Failed authentication
        app.logger.debug(f"delete_social(): Refusing permission for '{current_user.email}' and "
                         f"social_id = '{social_id}'.")
        EventRepository().log_event("Delete Social Fail", f"Refusing permission for '{current_user.email}', "
                                                f"social_id = '{social_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    #  Validate password
    # ----------------------------------------------------------- #
    # Need current user
    user = UserRepository().find_user_from_id(current_user.id)

    # Validate against current_user's password
    if not user.validate_password(user, password, user_ip):
        app.logger.debug(f"delete_social(): Delete failed, incorrect password for user_id = '{user.id}'!")
        EventRepository().log_event("Social Delete Fail", f"Incorrect password for user_id = '{user.id}'!")
        flash(f"Incorrect password for user {user.name}!")
        # Go back to socials page
        return redirect(url_for('display_socials'))  # type: ignore

    # ----------------------------------------------------------- #
    # Delete social
    # ----------------------------------------------------------- #
    if SocialRepository().delete_social(social_id):
        app.logger.debug(f"delete_social(): Deleted social, social_id = '{social_id}'.")
        EventRepository().log_event("Delete Social Success", f"Deleted social, social_id = '{social_id}'.")
        flash("Social has been deleted.")
    else:
        app.logger.debug(f"delete_social(): Failed to delete social, social_id = '{social_id}'.")
        EventRepository().log_event("Delete Social Fail", f"Failed to delete social, social_id = '{social_id}'.")
        flash("Sorry, something went wrong.")

    return redirect(url_for('display_socials'))  # type: ignore
