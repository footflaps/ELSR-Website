from flask import render_template, redirect, url_for, flash, request, abort, session, Response
from flask_login import login_user, current_user
from werkzeug import exceptions
from threading import Thread
import re

# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site, admin_email_address, admin_phone_number

# -------------------------------------------------------------------------------------------------------------- #
# Import our database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.user_repository import UserModel, UserRepository, DELETED_NAME, UNVERIFIED_PHONE_PREFIX
from core.forms.user_forms import CreateUserForm, VerifyUserForm, TwoFactorLoginForm, VerifySMSForm
from core.database.repositories.message_repository import MessageModel, MessageRepository, ADMIN_EMAIL
from core.database.repositories.event_repository import EventRepository
from core.subs_email import send_verification_email
from core.subs_sms import alert_admin_via_sms, send_sms_verif_code

from core.decorators.user_decorators import login_required, update_last_seen, logout_barred_user

# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

DEFAULT_EVENT_DAYS = 7


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Register new user
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/register', methods=['GET', 'POST'])
@update_last_seen
def register() -> Response | str:
    # Need a form
    form = CreateUserForm()

    # Detect form submission
    if form.validate_on_submit():
        # Grab credentials from form
        user_name = form.name.data.strip()
        user_email = form.email.data.strip()
        app.logger.debug(f"register(): Name = '{user_name}', Email = '{user_email}'")

        # Detect spam
        if "http" in user_name:
            flash("Sorry, you can't use links in your name.")
            return render_template("user_register.html", form=form, year=current_year, live_site=live_site(),
                                   admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)

        # Create a new User
        new_user = UserModel()
        new_user.name = user_name
        new_user.email = user_email

        # Does the user already exist?
        existing_user: UserModel | None = UserRepository.one_by_email(email=user_email)
        if existing_user:

            if existing_user.verified:
                # Email is validated, so they can just login
                app.logger.debug(f"register(): Duplicate email '{user_email}'.")
                EventRepository.log_event("Register Fail", f"Duplicate email '{user_email}'.")
                flash("You've already signed up with that email, log in instead!")
                return redirect(url_for('login', email=user_email))  # type: ignore

            else:
                # Email is registered, but unvalidated
                app.logger.debug(f"register(): Already signed up '{user_email}'.")
                EventRepository.log_event("Register Fail", f"Already signed up '{user_email}'.")
                flash("You've already signed up with that email, verify your email to login!")
                return redirect(url_for('validate_email'))  # type: ignore

        # We have a reserved name
        if new_user.name == DELETED_NAME:
            flash("Sorry, that name is reserved.")
            return render_template("user_register.html", form=form, year=current_year, live_site=live_site(),
                                   admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)

        # Names must be unique
        if UserRepository().check_name_in_use(name=new_user.name):
            app.logger.debug(f"user_page(): Username clash '{new_user.name}' for new_user.id = '{new_user.id}'.")
            EventRepository.log_event("User Page Success", f"Username clash '{new_user.name}' "
                                                           f"for new_user.id = '{new_user.id}'.")
            flash(f"Sorry, the name '{new_user.name.strip()}' is already in use!")
            return render_template("user_register.html", form=form, year=current_year, live_site=live_site(),
                                   admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)

        # Add to dB
        new_user = UserRepository.create_user(new_user=new_user, raw_password=form.password.data)  # type: ignore
        if new_user:
            # They now need to validate email address
            app.logger.debug(f"register(): Sending verification email to '{user_email}'.")
            EventRepository.log_event("Register Pass", f"Verification code sent to '{user_email}'.")
            flash("Please validate your email address with the code you have been sent.")
            # User threading as sending an email can take a while and we want a snappy website
            Thread(target=send_verification_email, args=(user_email, user_name, new_user.verification_code,)).start()
            return redirect(url_for('validate_email'))  # type: ignore

        else:
            # User already exists probably
            app.logger.debug(f"register(): User().create_user() failed for '{user_email}'.")
            EventRepository.log_event("Register Error", f"User().create_user() failed for '{user_email}'.")
            flash("Sorry, something went wrong!")
            return render_template("user_register.html", form=form, year=current_year, live_site=live_site(),
                                   admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)

    elif request.method == 'POST':
        flash("Something was missing in the registration form, see below!")
        return render_template("user_register.html", form=form, year=current_year, live_site=live_site(),
                               admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)

    # Show register page / form
    return render_template("user_register.html", form=form, year=current_year, live_site=live_site(),
                           admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)


# -------------------------------------------------------------------------------------------------------------- #
# Validate email address
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/validate_email', methods=['GET', 'POST'])
@update_last_seen
def validate_email() -> Response | str:
    # We support two entry modes to this page
    #  1. They click on a link in their email, and it makes a request with code and email fulfilled
    #  2. They go to this page and enter the details manually via the form

    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_code: str | None = request.args.get('code', None)
    user_email: str | None = request.args.get('email', None)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    # Only validate if we were actually sent them
    if user_email and user_code:

        # ----------------------------------------------------------- #
        # Method 1: the URL in the email passed through their params
        # ----------------------------------------------------------- #

        user_email = user_email.strip('"').strip("'")
        user: UserModel | None = UserRepository.one_by_email(email=user_email)
        if not user:
            # User doesn't exist
            app.logger.debug(f"validate_email(): URL route, can't find user email = '{user_email}'.")
            EventRepository.log_event("Validate Fail", f"URL route, can't find user email = '{user_email}'.")
            abort(404)

        if UserRepository.validate_email(user=user, code=user_code):
            # Success, user email validated!
            app.logger.debug(f"validate_email(): URL route, user '{user_email}' has been validated.")
            EventRepository.log_event("Validate Pass", f"URL route, user '{user_email}' has been validated.")
            flash("Email verified, please now log in!")

            # Send welcome email
            MessageRepository.send_welcome_message(target_email=user.email)

            # ----------------------------------------------------------- #
            # Alert admin via SMS
            # ----------------------------------------------------------- #
            sms_body = "New user joined. Remember to set write permissions for user."
            Thread(target=alert_admin_via_sms, args=(user, sms_body,)).start()

            # ----------------------------------------------------------- #
            # Alert admin via internal message
            # ----------------------------------------------------------- #
            admin_message = MessageModel(
                from_email=user.email,
                to_email=ADMIN_EMAIL,
                body="New user has joined - check permissions."
            )

            if MessageRepository.add_message(message=admin_message):
                # Success!
                app.logger.debug(f"validate_email(): User '{user.email}' has sent message to Admin.")
                EventRepository.log_event("Validate Pass", f"Message to Admin was sent successfully for '{user.email}'.")
            else:
                # Should never get here, but...
                app.logger.debug(f"validate_email(): Message().add_message() failed, user.email = '{user.email}'.")
                EventRepository.log_event("Validate Fail", f"Message send failed to Admin for '{user.email}'.")

            # ----------------------------------------------------------- #
            # Forward to login page
            # ----------------------------------------------------------- #
            return redirect(url_for('login', email=user_email))  # type: ignore

        # Fall through to form below

    # Need a form
    form = VerifyUserForm()

    # Detect form submission
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        # Method 2: They manually filled the form in
        # ----------------------------------------------------------- #

        # Grab credentials from form
        user_code = form.verification_code.data
        user_email = form.email.data

        # Find out user
        new_user: UserModel | None = UserRepository.one_by_email(email=user_email)  # type: ignore

        # Did we find that email address
        if new_user:

            # Already verified
            if new_user.verified:
                app.logger.debug(f"validate_email(): Form, user '{user_email}' is already validated.")
                EventRepository.log_event("Validate Fail", f"Form, user '{user_email}' is already validated.")
                flash("Email has already been verified! Log in with your password.")
                return redirect(url_for('login', email=str(user_email)))  # type: ignore

            # Check email exists in db
            if UserRepository.validate_email(user=new_user, code=str(user_code)):

                # Go to login page
                app.logger.debug(f"validate_email(): Form, user '{user_email}' has been validated.")
                EventRepository.log_event("Validate Pass", f"Form, user '{user_email}' has been validated.")
                flash("Email verified, please now log in!")

                # Send welcome message
                MessageRepository.send_welcome_message(target_email=str(user_email))

                # ----------------------------------------------------------- #
                # Alert admin via SMS
                # ----------------------------------------------------------- #
                sms_body = "New user joined. Remember to set write permissions for user."
                Thread(target=alert_admin_via_sms, args=(new_user, sms_body,)).start()

                # ----------------------------------------------------------- #
                # Alert admin via internal message
                # ----------------------------------------------------------- #
                admin_message = MessageModel(
                    from_email=user_email,
                    to_email=ADMIN_EMAIL,
                    body="New user has joined - check permissions."
                )

                if MessageRepository.add_message(admin_message):
                    # Success!
                    app.logger.debug(f"validate_email(): User '{user_email}' has sent message to Admin.")
                    EventRepository.log_event("Validate Pass", f"Message to Admin was sent successfully for '{user_email}'.")
                else:
                    # Should never get here, but...
                    app.logger.debug(f"validate_email(): Message().add_message() failed, user.email = '{user_email}'.")
                    EventRepository.log_event("Validate Fail", f"Message send failed to Admin for '{user_email}'.")

                # ----------------------------------------------------------- #
                # Forward to login page
                # ----------------------------------------------------------- #
                return redirect(url_for('login', email=new_user.email))  # type: ignore

            else:
                # Wrong code entered, or it's expired
                app.logger.debug(f"validate_email(): Form, code didn't work for user '{user_email}'.")
                EventRepository.log_event("Validate Fail", f"Form, code didn't work for user '{user_email}'.")
                flash("Incorrect code (or code has expired), please try again!")
                return render_template("user_validate.html", form=form, year=current_year, live_site=live_site())

        else:
            # Invalid email
            app.logger.debug(f"validate_email(): Form, unrecognised email '{user_email}'.")
            EventRepository.log_event("Validate Fail", f"Form, unrecognised email '{user_email}'.")
            flash("Unrecognised email, please try again!")
            # Just fall through to validate page

    # Show validate email form
    return render_template("user_validate.html", form=form, year=current_year, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# 2FA verification
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/twofa_login', methods=['GET', 'POST'])
@update_last_seen
def twofa_login() -> Response | str:
    # We support two entry modes to this page
    #  1. They click on a link in their email, and it makes a request with code and email fulfilled
    #  2. They go to this page and enter the details manually via the form

    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_code = request.args.get('code', None)
    user_email = request.args.get('email', None)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    # Only validate if we were actually sent them
    if user_email and user_code:

        # ----------------------------------------------------------- #
        # Method 1: the URL in the email passed through their params
        # ----------------------------------------------------------- #
        user_email = user_email.strip('"').strip("'")
        user: UserModel | None = UserRepository.one_by_email(email=user_email)
        if not user:
            # User doesn't exist
            app.logger.debug(f"twofa_login(): URL route, can't find user email = '{user_email}'.")
            EventRepository.log_event("2FA login Fail", f"URL route, can't find user email = '{user_email}'.")
            abort(404)

        if UserRepository.validate_sms(user=user, code=user_code):
            # Success, user validated!
            login_user(user=user, remember=True)
            flash(f"Welcome back {user.name}!")

            try:
                session['url']
            except Exception:
                session['url'] = url_for('display_blog')

            # Log event after they've logged in, so current_user can have an email address
            app.logger.debug(f"twofa_login(): User logged in for '{user_email}'.")
            EventRepository.log_event("Login", f"User logged in via 2FA, forwarding user '{user.email}' to '{session['url']}'.")

            # Return back to cached page
            app.logger.debug(f"login(): Success, forwarding user to '{session['url']}'.")
            return redirect(session['url'])  # type: ignore

        # Fall through to form below

    # Need a form
    form = TwoFactorLoginForm()

    # Detect form submission
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        # Method 2: They manually filled the form in
        # ----------------------------------------------------------- #
        user_code = form.verification_code.data
        user_email = form.email.data

        print(f"user_email = {user_email}")

        # Is that a valid email address?
        user = UserRepository.one_by_email(email=str(user_email))
        print(f"user = {user}")

        # Did we find that email address
        if user:

            if UserRepository.validate_sms(user=user, code=str(user_code)):
                # Success, 2FA complete!
                login_user(user=user, remember=True)
                flash(f"Welcome back {user.name}!")

                try:
                    session['url']
                except Exception:
                    session['url'] = url_for('display_blog')

                # Log event after they've logged in, so current_user can have an email address
                app.logger.debug(f"twofa_login(): User logged in for '{user_email}'.")
                EventRepository.log_event("Login",
                                          f"User logged in via 2FA, forwarding user '{user.email}' to '{session['url']}'.")

                # Return back to cached page
                app.logger.debug(f"login(): Success, forwarding user to '{session['url']}'.")
                return redirect(session['url'])  # type: ignore

            else:
                # Wrong code entered, or it's expired
                app.logger.debug(f"twofa_login(): Form, code didn't work for user '{user_email}'.")
                EventRepository.log_event("2FA login Fail", f"Form, code didn't work for user '{user_email}'.")
                flash("Incorrect code (or code has expired), please try again!")
                return render_template("user_sms_login.html", form=form, year=current_year, live_site=live_site())

        # Invalid email
        app.logger.debug(f"twofa_login(): Form, unrecognised email '{user_email}'.")
        EventRepository.log_event("2FA login Fail", f"Form, unrecognised email '{user_email}'.")
        flash("Unrecognised email, please try again!")

    # Show register page / form
    return render_template("user_sms_login.html", form=form, year=current_year, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Add a phone number
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/add_phone_number', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def add_phone_number() -> Response | str:
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    try:
        user_id: int | None = int(request.args.get('user_id', None))
    except ValueError:
        user_id = None

    try:
        phone_number = request.form['phone_number']
    except exceptions.BadRequestKeyError:
        phone_number = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"add_phone_number(): Missing user_id!")
        EventRepository.log_event("Add Phone Fail", f"Missing user id!")
        abort(400)
    if not phone_number:
        app.logger.debug(f"add_phone_number(): Missing user_id!")
        EventRepository.log_event("Add Phone Fail", f"Missing user id!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    try:
        user: UserModel | None = UserRepository.one_by_id(user_id=int(user_id))
    except Exception:
        user = None

    if not user:
        app.logger.debug(f"add_phone_number(): Invalid user user_id = '{user_id}'!")
        EventRepository.log_event("Add Phone Fail", f"Invalid user user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Check phone number
    # ----------------------------------------------------------- #
    # Strip all spaces
    phone_number = phone_number.strip().replace(" ", "")

    # Strip off UNVERIFIED_PHONE_PREFIX
    if phone_number[0:len(UNVERIFIED_PHONE_PREFIX)] == UNVERIFIED_PHONE_PREFIX:
        phone_number = phone_number[len(UNVERIFIED_PHONE_PREFIX):len(phone_number)]

    # Check for UK code
    if phone_number[0:3] != "+44":
        flash("Phone number must start with '+44'!")
        return redirect(url_for('user_page', user_id=user_id))  # type: ignore

    # Strip any non digits (inc leading '+')
    phone_number = re.sub('[^0-9]', '', phone_number)
    if len(phone_number) != 12:
        flash("Phone number must be 12 digis long eg '+44 1234 123456'!")
        return redirect(url_for('user_page', user_id=user_id))  # type: ignore

    # Add back leading '+'
    phone_number = "+" + phone_number
    print(f"'{phone_number}'")

    # ----------------------------------------------------------- #
    # Restrict access (Admin or user themselves)
    # ----------------------------------------------------------- #
    if int(current_user.id) != int(user_id) and \
            not current_user.admin:
        app.logger.debug(f"add_phone_number(): User isn't allowed "
                         f"current_user.id='{current_user.id}', user_id='{user_id}'.")
        EventRepository.log_event("Add Phone Fail", f"User isn't allowed "
                                                    f"current_user.id='{current_user.id}', user_id='{user_id}'.")
        abort(403)

    # ----------------------------------------------------------- #
    # Update phone number
    # ----------------------------------------------------------- #
    if UserRepository.set_phone_number(user_id, UNVERIFIED_PHONE_PREFIX + phone_number):

        # Now generate a verification code
        if UserRepository.generate_sms_code(user_id=user_id):
            # Reacquire user
            user = UserRepository.one_by_id(user_id=user_id)
            # Send the code to the user
            send_sms_verif_code(user=user)  # type: ignore
            app.logger.debug(f"add_phone_number(): SMS code sent, user_id='{user_id}'.")
            EventRepository.log_event("Add Phone Pass", f"SMS code sent, user_id='{user_id}'.")
            flash(f"A verification code has been sent to '{phone_number}'.")
            return redirect(url_for('mobile_verify', user_id=user_id))  # type: ignore

        else:
            # Should never get here, but...
            app.logger.debug(f"add_phone_number(): User().generate_sms_code() failed, user_id='{user_id}'.")
            EventRepository.log_event("Add Phone Fail", f"User().generate_sms_code() failed, user_id='{user_id}'.")
            flash("Sorry, something went wrong!")

    else:
        # Should never get here, but...
        app.logger.debug(f"add_phone_number(): User().set_phone_number() failed, user_id='{user_id}'.")
        EventRepository.log_event("Add Phone Fail", f"User().set_phone_number() failed, user_id='{user_id}'.")
        flash("Sorry, something went wrong!")

    # Back to user page
    return redirect(url_for('user_page', user_id=user_id))  # type: ignore


# -------------------------------------------------------------------------------------------------------------- #
# Verify phone number
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/mobile_verify', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def mobile_verify() -> Response | str:
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"mobile_verify(): Missing user_id!")
        EventRepository.log_event("Verify Mobile Fail", f"Missing user id!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user: UserModel | None = UserRepository.one_by_id(user_id)
    if not user:
        app.logger.debug(f"mobile_verify(): Invalid user user_id = '{user_id}'!")
        EventRepository.log_event("Verify Mobile Fail", f"Invalid user user_id = '{user_id}'.")
        abort(404)

    # Need a form
    form = VerifySMSForm()

    # Detect form submission
    if form.validate_on_submit():
        # ----------------------------------------------------------- #
        # POST:
        # ----------------------------------------------------------- #
        # Get code from the form
        code = form.verification_code.data

        if UserRepository.validate_sms(user, code):
            # Success, user validated!
            login_user(user, remember=True)
            flash(f"Mobile number has been verified!")

            # Log event after they've logged in, so current_user can have an email address
            app.logger.debug(f"mobile_verify(): Mobile verified for user_id = '{user_id}'.")
            EventRepository.log_event("Verify Mobile Pass", f"Mobile verified for user_id = '{user_id}'.")

            # Return back to user page
            return redirect(url_for('user_page', user_id=user_id))  # type: ignore

        else:
            # Incorrect code...
            flash("Sorry, that code is either wrong or has expired.")
            # Fal back to the GET option

    # Back to user page
    return render_template("user_phone_verification.html", year=current_year, form=form, live_site=live_site())
