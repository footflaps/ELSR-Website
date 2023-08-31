from flask import render_template, redirect, url_for, flash, request, abort, session, make_response
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug import exceptions
from urllib.parse import urlparse
from threading import Thread
import os
import re


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year


# -------------------------------------------------------------------------------------------------------------- #
# Import our database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, CreateUserForm, VerifyUserForm, LoginUserForm, ResetPasswordForm, \
    admin_only, update_last_seen, logout_barred_user, UNVERIFIED_PHONE_PREFIX, VerifySMSForm, \
    TwoFactorLoginForm, DELETED_NAME, ChangeUserNameForm
from core.dB_cafes import Cafe, OPEN_CAFE_COLOUR, CLOSED_CAFE_COLOUR
from core.dB_gpx import Gpx
from core.dB_cafe_comments import CafeComment
from core.db_messages import Message, ADMIN_EMAIL
from core.dB_events import Event
from core.subs_email_sms import send_reset_email, send_verification_email, send_2fa_sms, send_sms_verif_code
from core.subs_google_maps import MAP_BOUNDS, GOOGLE_MAPS_API_KEY
from core.db_calendar import Calendar
from core.db_social import Socials
from core.subs_email_sms import alert_admin_via_sms


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

DEFAULT_EVENT_DAYS = 7

# This is the admin email address
admin_email_address = os.environ['ELSR_ADMIN_EMAIL']
admin_phone_number = os.environ['ELSR_TWILIO_NUMBER']


# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #

def same_origin(current_uri, compare_uri):
    current = urlparse(current_uri)
    compare = urlparse(compare_uri)

    return (
            current.scheme == compare.scheme
            and current.hostname == compare.hostname
            and current.port == compare.port
    )


def validate_phone_number(phone_number):
    # ----------------------------------------------------------- #
    # Check phone number
    # ----------------------------------------------------------- #
    # Strip all spaces
    phone_number = phone_number.strip().replace(" ", "")
    print(f"'{phone_number}', '{phone_number[0:2]}'")

    # Check for UK code
    if phone_number[0:3] != "+44":
        flash("Phone number must start with '+44'!")
        return None

    # Strip any non digits (inc leading '+')
    phone_number = re.sub('[^0-9]', '', phone_number)
    if len(phone_number) != 12:
        flash("Phone number must be 12 digis long eg '+44 1234 123456'!")
        return None

    # Add back leading '+'
    phone_number = "+" + phone_number
    return phone_number


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Login
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/login', methods=['GET', 'POST'])
@update_last_seen
def login():
    # ----------------------------------------------------------- #
    # Get details from the page (optional)
    # ----------------------------------------------------------- #
    email = request.args.get('email', None)
    app.logger.debug(f"login(): Passed email = '{email}'.")

    # ----------------------------------------------------------- #
    # Need a login form
    # ----------------------------------------------------------- #
    form = LoginUserForm()
    if email:
        form.email.data = email

    # Detect form submission
    if form.validate_on_submit():

        # ------------------------------------------------------------------------------------------------- #
        #   POST - login attempt via form                                                                   #
        # ------------------------------------------------------------------------------------------------- #

        # Get login details
        email = form.email.data
        password = form.password.data

        # Get user's IP
        if request.headers.getlist("X-Forwarded-For"):
            user_ip = request.headers.getlist("X-Forwarded-For")[0]
        else:
            user_ip = request.remote_addr

        # See if user exists by looking up their email address
        user = User().find_user_from_email(email)

        # Test 1: Does the user exist?
        if not user:
            app.logger.debug(f"login(): email not recognised '{email}'.")
            Event().log_event("Login Fail", f"Email not recognised '{email}'")
            flash("Email address is not recognised!")
            return render_template("user_login.html", form=form, year=current_year)

        # Test 2: Did they forget password?
        if form.forgot.data:
            # Don't check return status as we don't want to give anything away
            app.logger.debug(f"login(): Recovery email requested for '{email}'.")
            Event().log_event("Login Fail", f"Recovery email requested for '{email}'.")
            # Generate a new code
            User().create_new_reset_code(email)
            # Find the user to get the details
            user = User().find_user_from_email(email)
            # Send an email
            Thread(target=send_reset_email, args=(user.email, user.name, user.reset_code,)).start()
            # Tell user to expect an email
            flash("If your email address is registered, an email recovery mail has been sent.")
            return render_template("user_login.html", form=form, year=current_year)

        # Test 3: Do they want a new verification code?
        if form.verify.data:
            app.logger.debug(f"login(): Reset email requested for '{email}'.")
            Event().log_event("Login Fail", f"Reset email requested for '{email}'.")
            # Generate a new code
            User().create_new_verification(user.id)
            # Find the user to get the details
            user = User().find_user_from_email(email)
            # Send an email
            Thread(target=send_verification_email, args=(user.email, user.name, user.verification_code,)).start()
            # Tell user to expect an email
            flash("If your email address is registered, a new verification code has been sent.")
            return redirect(url_for('validate_email'))

        # Test 4: Is the user validated?
        if not user.verified():
            app.logger.debug(f"login(): Failed, Email not verified yet '{email}'.")
            Event().log_event("Login Fail", f"Email not verified yet '{email}'.")
            flash("That email address has not been verified yet!")
            return redirect(url_for('validate_email'))

        # Test 5: Is the user barred?
        if user.blocked():
            app.logger.debug(f"login(): Failed, Email has been blocked '{email}'.")
            Event().log_event("Login Fail", f"Email has been blocked '{email}'.")
            flash("That email address has been temporarily blocked!")
            flash(f"Contact '{admin_email_address}' to discuss.")
            return render_template("user_login.html", form=form, year=current_year)

        # Test 6: Check password
        if User().validate_password(user, password, user_ip):
            # Admins require 2FA and we'll offer it to anyone with a phone number validated
            if user.admin() or \
                    user.has_valid_phone_number():
                # Admins must use 2FA via SMS
                User().generate_sms_code(user.id)
                flash(f"2FA code has been sent to '{user.phone_number}'.")
                user = User().find_user_from_id(user.id)
                send_2fa_sms(user)
                return redirect(url_for('twofa_login'))

            else:
                # Non Admin, so we can login now
                login_user(user, remember=True)

                # Log event after they've logged in
                flash(f"Welcome back {user.name}!")
                app.logger.debug(f"login(): User logged in for '{email}'.")
                Event().log_event("Login", f"User logged in, forwarding user '{email}' to '{session['url']}'.")

                # Return back to cached page
                app.logger.debug(f"login(): Success, forwarding user to '{session['url']}'.")
                return redirect(session['url'])

        else:
            # Login failed
            app.logger.debug(f"login(): Failed, Wrong password for '{email}'.")
            Event().log_event("Login Fail", f"Wrong password for '{email}'")
            flash("Password did not match!")
            return render_template("user_login.html", form=form, year=current_year)

    # ------------------------------------------------------------------------------------------------- #
    #   GET - Show login page                                                                           #
    # ------------------------------------------------------------------------------------------------- #

    # Our current domain
    good_referrer = 'https://{0}/'.format(request.host)

    # Cache the calling referring page, so we can return to that after a successful login
    if not same_origin(request.referrer, good_referrer) \
            or "validate_email" in str(request.referrer) \
            or "reset" in str(request.referrer):
        # If they've come from validate email, no point bouncing them back once they've logged in,
        # so forward them to home instead. Likewise, if they came from another site, don't jump back after login.
        session['url'] = url_for('home')
    else:
        session['url'] = request.referrer

    app.logger.debug(f"login(): Saved '{session['url']}' as return page after login.")

    return render_template("user_login.html", form=form, year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# Log out
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/logout')
@update_last_seen
def logout():
    # Have to log the event before we log out, so we still have their email address
    app.logger.debug(f"logout(): Logging user '{current_user.email}' out now...")
    Event().log_event("Logout", f"User '{current_user.email}' logged out.")
    flash("You have been logged out!")

    # Logout the user
    logout_user()

    # Clear the session
    session.clear()

    # Delete the user's "remember me" cookie as apparently logout doesn't do that
    # From: https://stackoverflow.com/questions/25144092/flask-login-still-logged-in-after-use-logouts-when-using-remember-me
    # This seems to work now....
    response = make_response(redirect(url_for('home')))
    response.delete_cookie(app.config['REMEMBER_COOKIE_NAME'])
    return response


# -------------------------------------------------------------------------------------------------------------- #
# Register new user
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/register', methods=['GET', 'POST'])
@update_last_seen
def register():
    # Need a form
    form = CreateUserForm()

    # Detect form submission
    if form.validate_on_submit():

        # Grab credentials from form
        new_user = User()
        new_user.name = form.name.data
        new_user.email = form.email.data
        app.logger.debug(f"register(): new_user = '{new_user}', new_user.name = '{new_user.name}', "
                         f"new_user.email = '{new_user.email}'")

        # Does the user already exist?
        if User().find_user_from_email(new_user.email):

            if User().find_user_from_email(new_user.email).verified():
                # Email is validated, so they can just login
                app.logger.debug(f"register(): Duplicate email '{new_user.email}'.")
                Event().log_event("Register Fail", f"Duplicate email '{new_user.email}'.")
                flash("You've already signed up with that email, log in instead!")
                return redirect(url_for('login', email=new_user.email))

            else:
                # Email is registered, but unvalidated
                app.logger.debug(f"register(): Already signed up '{new_user.email}'.")
                Event().log_event("Register Fail", f"Already signed up '{new_user.email}'.")
                flash("You've already signed up with that email, verify your email to login!")
                return redirect(url_for('validate_email'))

        # We have a reserved name
        if new_user.name == DELETED_NAME:
            flash("Sorry, that name is reserved.")
            return render_template("user_register.html", form=form, year=current_year,
                                   admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)

        # Names must be unique
        if User().check_name_in_use:
            flash(f"Sorry, the name '{new_user.name.strip()}' is already in use!")
            return render_template("user_register.html", form=form, year=current_year,
                                   admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)

        # Add to dB
        if User().create_user(new_user, form.password.data):

            # Debug
            user = User().find_user_from_email(form.email.data)

            # They now need to validate email address
            app.logger.debug(f"register(): Sending verification email to '{user.email}'.")
            Event().log_event("Register Pass", f"Verification code sent to '{user.email}'.")
            flash("Please validate your email address with the code you have been sent.")
            # User threading as sending an email can take a while and we want a snappy website
            Thread(target=send_verification_email, args=(user.email, user.name, user.verification_code,)).start()
            return redirect(url_for('validate_email'))

        else:
            # User already exists probably
            app.logger.debug(f"register(): User().create_user() failed for '{new_user.email}'.")
            Event().log_event("Register Error", f"User().create_user() failed for '{new_user.email}'.")
            flash("Sorry, something went wrong!")
            return render_template("user_register.html", form=form, year=current_year,
                                   admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)

    elif request.method == 'POST':
        flash("Something was missing in the registration form, see below!")
        return render_template("user_register.html", form=form, year=current_year,
                               admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)

    # Show register page / form
    return render_template("user_register.html", form=form, year=current_year,
                           admin_email_address=admin_email_address, admin_phone_number=admin_phone_number)


# -------------------------------------------------------------------------------------------------------------- #
# Validate email address
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/validate_email', methods=['GET', 'POST'])
@update_last_seen
def validate_email():
    # We support two entry modes to this page
    #  1. They click on a link in their email and it makes a request with code and email fulfilled
    #  2. They go to this page and enter the details manually via the form

    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    code = request.args.get('code', None)
    email = request.args.get('email', None)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    # Only validate if we were actually sent them
    if email and code:

        # ----------------------------------------------------------- #
        # Method 1: the URL in the email passed through their params
        # ----------------------------------------------------------- #

        email = email.strip('"').strip("'")
        user = User().find_user_from_email(email)
        if not user:
            # User doesn't exist
            app.logger.debug(f"validate_email(): URL route, can't find user email = '{email}'.")
            Event().log_event("Validate Fail", f"URL route, can't find user email = '{email}'.")
            abort(404)

        if User().validate_email(user, code):
            # Success, user email validated!
            app.logger.debug(f"validate_email(): URL route, user '{email}' has been validated.")
            Event().log_event("Validate Pass", f"URL route, user '{email}' has been validated.")
            flash("Email verified, please now log in!")

            # Send welcome email
            Message().send_welcome_message(user.email)

            # Forward to login page
            return redirect(url_for('login', email=email))

        # Fall through to form below

    # Need a form
    form = VerifyUserForm()

    # Detect form submission
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        # Method 2: They manually filled the form in
        # ----------------------------------------------------------- #

        # Grab credentials from form
        new_user = User()
        new_user.email = form.email.data
        code = form.verification_code.data

        # Find out user
        user = User().find_user_from_email(new_user.email)

        # Did we find that email address
        if user:

            # Already verified
            if user.verified():
                app.logger.debug(f"validate_email(): Form, user '{user.email}' is already validated.")
                Event().log_event("Validate Fail", f"Form, user '{user.email}' is already validated.")
                flash("Email has already been verified! Log in with your password.")
                return redirect(url_for('login', email=new_user.email))

            # Valid email
            if User().validate_email(user, code):

                # Debug
                user = User().find_user_from_email(form.email.data)

                # Go to login page
                app.logger.debug(f"validate_email(): Form, user '{user.email}' has been validated.")
                Event().log_event("Validate Pass", f"Form, user '{user.email}' has been validated.")
                flash("Email verified, please now log in!")

                # Send welcome email
                Message().send_welcome_message(new_user.email)

                # ----------------------------------------------------------- #
                # Alert admin via SMS
                # ----------------------------------------------------------- #
                message = "New user joined. Remember to set write permissions for user."
                Thread(target=alert_admin_via_sms, args=(user, message,)).start()

                # ----------------------------------------------------------- #
                # Alert admin via internal message
                # ----------------------------------------------------------- #
                message = Message(
                    from_email=user.email,
                    to_email=ADMIN_EMAIL,
                    body="New user has joined - check permissions."
                )

                if Message().add_message(message):
                    # Success!
                    app.logger.debug(f"validate_email(): User '{user.email}' has sent message to Admin.")
                    Event().log_event("Validate Pass", f"Message to Admin was sent successfully.")
                else:
                    # Should never get here, but...
                    app.logger.debug(f"validate_email(): Message().add_message() failed, user.email = '{user.email}'.")
                    Event().log_event("Validate Fail", f"Message send failed to Admin!")

                # ----------------------------------------------------------- #
                # Forward to login page
                # ----------------------------------------------------------- #
                return redirect(url_for('login', email=new_user.email))

            else:
                # Wrong code entered, or it's expired
                app.logger.debug(f"validate_email(): Form, code didn't work for user '{user.email}'.")
                Event().log_event("Validate Fail", f"Form, code didn't work for user '{user.email}'.")
                flash("Incorrect code (or code has expired), please try again!")
                return render_template("user_validate.html", form=form, year=current_year)

        # Invalid email
        app.logger.debug(f"validate_email(): Form, unrecognised email '{new_user.email}'.")
        Event().log_event("Validate Fail", f"Form, unrecognised email '{new_user.email}'.")
        flash("Unrecognised email, please try again!")

    # Show register page / form
    return render_template("user_validate.html", form=form, year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# 2FA verification
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/twofa_login', methods=['GET', 'POST'])
@update_last_seen
def twofa_login():
    # We support two entry modes to this page
    #  1. They click on a link in their email and it makes a request with code and email fulfilled
    #  2. They go to this page and enter the details manually via the form

    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    code = request.args.get('code', None)
    email = request.args.get('email', None)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    # Only validate if we were actually sent them
    if email and code:

        # ----------------------------------------------------------- #
        # Method 1: the URL in the email passed through their params
        # ----------------------------------------------------------- #

        email = email.strip('"').strip("'")
        user = User().find_user_from_email(email)
        if not user:
            # User doesn't exist
            app.logger.debug(f"twofa_login(): URL route, can't find user email = '{email}'.")
            Event().log_event("2FA login Fail", f"URL route, can't find user email = '{email}'.")
            abort(404)

        if User().validate_sms(user, code):
            # Success, user validated!
            login_user(user, remember=True)
            flash(f"Welcome back {user.name}!")

            # Log event after they've logged in, so current_user can have an email address
            app.logger.debug(f"twofa_login(): User logged in for '{email}'.")
            Event().log_event("Login", f"User logged in via 2FA, forwarding user '{user.email}' to '{session['url']}'.")

            # Return back to cached page
            app.logger.debug(f"login(): Success, forwarding user to '{session['url']}'.")
            return redirect(session['url'])

        # Fall through to form below

    # Need a form
    form = TwoFactorLoginForm()

    # Detect form submission
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        # Method 2: They manually filled the form in
        # ----------------------------------------------------------- #

        # Is that a valid email address?
        user = User().find_user_from_email(form.email.data)

        # Did we find that email address
        if user:

            # Verify their SMS code
            code = form.verification_code.data

            if User().validate_sms(user, code):
                # Success, 2FA complete!
                login_user(user, remember=True)
                flash(f"Welcome back {user.name}!")

                # Log event after they've logged in, so current_user can have an email address
                app.logger.debug(f"twofa_login(): User logged in for '{email}'.")
                Event().log_event("Login",
                                  f"User logged in via 2FA, forwarding user '{user.email}' to '{session['url']}'.")

                # Return back to cached page
                app.logger.debug(f"login(): Success, forwarding user to '{session['url']}'.")
                return redirect(session['url'])

            else:
                # Wrong code entered, or it's expired
                app.logger.debug(f"twofa_login(): Form, code didn't work for user '{user.email}'.")
                Event().log_event("2FA login Fail", f"Form, code didn't work for user '{user.email}'.")
                flash("Incorrect code (or code has expired), please try again!")
                return render_template("user_sms_login.html", form=form, year=current_year)

        # Invalid email
        app.logger.debug(f"twofa_login(): Form, unrecognised email '{form.email.data}'.")
        Event().log_event("2FA login Fail", f"Form, unrecognised email '{form.email.data}'.")
        flash("Unrecognised email, please try again!")

    # Show register page / form
    return render_template("user_sms_login.html", form=form, year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# Reset password
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/reset', methods=['GET', 'POST'])
@update_last_seen
def reset_password():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    code = request.args.get('code', None)
    email = request.args.get('email', None)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    # Only validate if we were actually sent them
    if email and code:
        email = email.strip('"').strip("'")
        user = User().find_user_from_email(email)
        if not user:
            app.logger.debug(f"reset_password(): URL route, invalid email = '{email}'.")
            Event().log_event("Reset Fail", f"URL route, invalid email = '{email}'.")
            abort(404)
        if not User().validate_reset_code(user.id, int(code)):
            app.logger.debug(f"reset_password(): URL route, invalid email = '{code}', for user = '{user.email}'.")
            Event().log_event("Reset Fail", f"URL route, invalid email = '{code}', for user = '{user.email}'.")
            abort(404)

    # ----------------------------------------------------------- #
    # Create form
    # ----------------------------------------------------------- #
    form = ResetPasswordForm()
    form.email.data = email

    # Detect form submission
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        # POST: reset password form completed
        # ----------------------------------------------------------- #
        # This may have changed!
        email = form.email.data

        if form.password1.data != form.password2.data:
            app.logger.debug(f"reset_password(): Form route, Passwords don't match! Email = '{email}'.")
            Event().log_event("Reset Fail", f"Form route, Passwords don't match! Email = '{email}'.")
            flash("Passwords don't match!")
            # Back to the same page for another try
            return render_template("user_reset_password.html", form=form, year=current_year)

        if User().reset_password(email, form.password1.data):
            app.logger.debug(f"reset_password(): Form route, Password has been reset, email = '{email}'.")
            Event().log_event("Reset Success", f"Form route, Password has been reset, email = '{email}'.")
            flash("Password has been reset, please login!")
            # Forward to login page
            return redirect(url_for('login', email=email))
        else:
            # Should never happen, but...
            app.logger.debug(f"reset_password(): User().reset_password() failed! email = '{email}'.")
            Event().log_event("Reset Fail", f"User().reset_password() failed! email = '{email}'.")
            flash("Sorry, something went wrong!")

    return render_template("user_reset_password.html", form=form, year=current_year)


# -------------------------------------------------------------------------------------------------------------- #
# User home page
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/user_page', methods=['GET', 'POST'])
@login_required
@update_last_seen
def user_page():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)  # Mandatory
    event_period = request.args.get('days', None)  # Optional
    anchor = request.args.get('anchor', None)  # Optional

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"user_page(): Missing user_id!")
        Event().log_event("User Page Fail", f"Missing user_id!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"user_page(): Invalid user user_id = '{user_id}'!")
        Event().log_event("User Page Fail", f"Invalid user_id = '{user_id}'.")
        abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    #  1. Admin can see any user's page
    #  2. A user can see their page
    #  3. Deleted users pages are denied
    if int(current_user.id) != int(user_id) and \
            not current_user.admin() or \
            user.name == DELETED_NAME:
        app.logger.debug(f"user_page(): Rejected request from current_user.id = '{current_user.id}', "
                         f"for user_id = '{user_id}'.")
        Event().log_event("User Page Fail", f"Rejected request from current_user.id = '{current_user.id}', "
                                            f"for user_id = '{user_id}'.")
        abort(403)

    # ----------------------------------------------------------- #
    # Need a form
    # ----------------------------------------------------------- #
    form = ChangeUserNameForm()

    if request.method == 'GET':
        # pre-fill existing name
        form.name.data = user.name
    elif form.validate_on_submit():
        # User has requested new name
        new_name = form.name.data.strip()
        if new_name == user.name:
            # No change
            flash("That's the same name as before!")
            return redirect(url_for('user_page', user_id=user.id))
        elif User().check_name_in_use(new_name):
            # Not unique
            flash(f"Sorry, the name '{new_name}' is already in use!")
            return redirect(url_for('user_page', user_id=user.id))
        else:
            # Change their name
            if User().update_user_name(user.id, new_name):
                app.logger.debug(f"user_page(): Change username for user_id = '{user_id}' to '{new_name}'.")
                Event().log_event("User Page Succes", f"Changed username for user_id = '{user_id}' to '{new_name}'.")
                flash("User name has been changed!")
                return redirect(url_for('user_page', user_id=user.id))
            else:
                # Should never get here, but..
                app.logger.debug(f"user_page(): Failed to change username for user_id = '{user_id}'.")
                Event().log_event("User Page Fail",
                                  f"Failed to change username for user_id = '{user_id}'.")
                flash("Sorry, something went wrong!")
                return redirect(url_for('user_page', user_id=user.id))

    elif request.method == 'POST':
        # Failed form validation
        flash("You didn't fill your name in properly!")
        return redirect(url_for('user_page', user_id=user.id))

    # ----------------------------------------------------------- #
    # Events
    # ----------------------------------------------------------- #
    if not event_period:
        events = Event().all_events_email_days(user.email, DEFAULT_EVENT_DAYS)
        days = DEFAULT_EVENT_DAYS
    elif event_period == "all":
        events = Event().all_events_email(user.email)
        days = "all"
    else:
        events = Event().all_events_email_days(user.email, int(event_period))
        days = int(event_period)

    # ----------------------------------------------------------- #
    # Cafes
    # ----------------------------------------------------------- #
    cafes = Cafe().find_all_cafes_by_email(user.email)

    # ----------------------------------------------------------- #
    # GPX files
    # ----------------------------------------------------------- #
    gpxes = Gpx().all_gpxes_by_email(user.email)

    # ----------------------------------------------------------- #
    # Comments
    # ----------------------------------------------------------- #
    cafe_comments = CafeComment().all_comments_by_email(user.email)

    # ----------------------------------------------------------- #
    # Messages
    # ----------------------------------------------------------- #
    messages = Message().all_messages_to_email(user.email)

    # Any unread?
    count = 0
    for message in messages:
        if message.from_email == ADMIN_EMAIL:
            message.from_name = "Admin team"
        else:
            message.from_name = User().find_user_from_email(message.from_email).name
        if not message.been_read():
            count += 1

    if count > 0:
        if count == 1:
            flash(f"You have {count} unread message")
        else:
            flash(f"You have {count} unread messages")

    # ----------------------------------------------------------- #
    # Rides
    # ----------------------------------------------------------- #
    rides = Calendar().all_calendar_email(user.email)

    # ----------------------------------------------------------- #
    # All scheduled social events
    # ----------------------------------------------------------- #
    socials = Socials().all_by_email(user.email)

    # ----------------------------------------------------------- #
    # Markers for Google Map of User's Cafes
    # ----------------------------------------------------------- #
    cafe_markers = []
    mean_lat = 0
    mean_lon = 0
    num_cafes = 0

    for cafe in cafes:
        if cafe.active:
            colour = OPEN_CAFE_COLOUR
        else:
            colour = CLOSED_CAFE_COLOUR

        cafe_marker = {
            "position": {"lat": cafe.lat, "lng": cafe.lon},
            "title": f'<a href="{url_for("cafe_details", cafe_id=cafe.id)}">{cafe.name}</a>',
            "color": colour,
        }
        # Add to list
        cafe_markers.append(cafe_marker)

        # Need central position for map view
        mean_lat += cafe.lat
        mean_lon += cafe.lon
        num_cafes += 1

    # Map will launch centered here
    if num_cafes > 0:
        map_coords = {"lat": mean_lat/num_cafes, "lng": mean_lon/num_cafes}
    else:
        map_coords = {"lat": 0, "lng": 0}

    # -------------------------------------------------------------------------------------------- #
    # Show user page
    # -------------------------------------------------------------------------------------------- #
    if anchor == "messages":
        return render_template("user_page.html", year=current_year, cafes=cafes, user=user, gpxes=gpxes,
                               cafe_comments=cafe_comments, messages=messages, events=events, days=days,
                               cafe_markers=cafe_markers, map_coords=map_coords, rides=rides, socials=socials,
                               GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY, MAP_BOUNDS=MAP_BOUNDS, form=form,
                               anchor="messages")

    elif event_period or anchor == "eventLog":
        return render_template("user_page.html", year=current_year, cafes=cafes, user=user, gpxes=gpxes,
                               cafe_comments=cafe_comments, messages=messages, events=events, days=days,
                               cafe_markers=cafe_markers, map_coords=map_coords, rides=rides, socials=socials,
                               GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY, MAP_BOUNDS=MAP_BOUNDS, form=form,
                               anchor="eventLog")

    else:
        return render_template("user_page.html", year=current_year, cafes=cafes, user=user, gpxes=gpxes,
                               cafe_comments=cafe_comments, messages=messages, events=events, days=days,
                               cafe_markers=cafe_markers, map_coords=map_coords, rides=rides, socials=socials,
                               GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY, MAP_BOUNDS=MAP_BOUNDS, form=form)


# -------------------------------------------------------------------------------------------------------------- #
# Add a phone number
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/add_phone_number', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def add_phone_number():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)
    try:
        phone_number = request.form['phone_number']
    except exceptions.BadRequestKeyError:
        phone_number = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"add_phone_number(): Missing user_id!")
        Event().log_event("Add Phone Fail", f"Missing user id!")
        abort(400)
    if not phone_number:
        app.logger.debug(f"add_phone_number(): Missing user_id!")
        Event().log_event("Add Phone Fail", f"Missing user id!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"add_phone_number(): Invalid user user_id = '{user_id}'!")
        Event().log_event("Add Phone Fail", f"Invalid user user_id = '{user_id}'.")
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
        return redirect(url_for('user_page', user_id=user_id))

    # Strip any non digits (inc leading '+')
    phone_number = re.sub('[^0-9]', '', phone_number)
    if len(phone_number) != 12:
        flash("Phone number must be 12 digis long eg '+44 1234 123456'!")
        return redirect(url_for('user_page', user_id=user_id))

    # Add back leading '+'
    phone_number = "+" + phone_number
    print(f"'{phone_number}'")

    # ----------------------------------------------------------- #
    # Restrict access (Admin or user themselves)
    # ----------------------------------------------------------- #
    if int(current_user.id) != int(user_id) and \
            not current_user.admin():
        app.logger.debug(f"add_phone_number(): User isn't allowed "
                         f"current_user.id='{current_user.id}', user_id='{user_id}'.")
        Event().log_event("Add Phone Fail", f"User isn't allowed "
                                            f"current_user.id='{current_user.id}', user_id='{user_id}'.")
        abort(403)

    # ----------------------------------------------------------- #
    # Update phone number
    # ----------------------------------------------------------- #
    if User().set_phone_number(user_id, UNVERIFIED_PHONE_PREFIX + phone_number):

        # Now generate a verification code
        if User().generate_sms_code(user_id):
            # Reacquire user
            user = User().find_user_from_id(user_id)
            # Send the code to the user
            send_sms_verif_code(user)
            app.logger.debug(f"add_phone_number(): SMS code sent, user_id='{user_id}'.")
            Event().log_event("Add Phone Pass", f"SMS code sent, user_id='{user_id}'.")
            flash(f"A verification code has been sent to '{phone_number}'.")
            return redirect(url_for('mobile_verify', user_id=user_id))

        else:
            # Should never get here, but...
            app.logger.debug(f"add_phone_number(): User().generate_sms_code() failed, user_id='{user_id}'.")
            Event().log_event("Add Phone Fail", f"User().generate_sms_code() failed, user_id='{user_id}'.")
            flash("Sorry, something went wrong!")
    else:
        # Should never get here, but...
        app.logger.debug(f"add_phone_number(): User().set_phone_number() failed, user_id='{user_id}'.")
        Event().log_event("Add Phone Fail", f"User().set_phone_number() failed, user_id='{user_id}'.")
        flash("Sorry, something went wrong!")

    # Back to user page
    return redirect(url_for('user_page', user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Verify phone number
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/mobile_verify', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def mobile_verify():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"mobile_verify(): Missing user_id!")
        Event().log_event("Verify Mobile Fail", f"Missing user id!")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"mobile_verify(): Invalid user user_id = '{user_id}'!")
        Event().log_event("Verify Mobile Fail", f"Invalid user user_id = '{user_id}'.")
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

        if User().validate_sms(user, code):
            # Success, user validated!
            login_user(user, remember=True)
            flash(f"Mobile number has been verified!")

            # Log event after they've logged in, so current_user can have an email address
            app.logger.debug(f"mobile_verify(): Mobile verified for user_id = '{user_id}'.")
            Event().log_event("Verify Mobile Pass", f"Mobile verified for user_id = '{user_id}'.")

            # Return back to user page
            return redirect(url_for('user_page', user_id=user_id))

        else:
            # Incorrect code...
            flash("Sorry, that code is either wrong or has expired.")
            # Fal back to the GET option

    # Back to user page
    return render_template("user_phone_verification.html", year=current_year, form=form)


# -------------------------------------------------------------------------------------------------------------- #
# Delete user - user can delete themselves so not restricted to Admin only
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/delete_user', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def delete_user():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)
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
    if not user_id:
        app.logger.debug(f"delete_user(): Missing user_id!")
        Event().log_event("Delete User Fail", f"missing user id")
        abort(400)
    elif not password:
        app.logger.debug(f"delete_user(): Missing user password!")
        Event().log_event("Delete User Fail", f"Missing user password")
        abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)
    if not user:
        app.logger.debug(f"delete_user(): Invalid user user_id = '{user_id}'!")
        Event().log_event("Delete User Fail", f"Invalid user user_id = '{user_id}'!")
        abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    if int(current_user.id) != int(user_id) and \
            not current_user.admin():
        app.logger.debug(f"delete_user(): User isn't allowed "
                         f"current_user.id='{current_user.id}', user_id='{user_id}'.")
        Event().log_event("Delete User Fail", f"User isn't allowed "
                                              f"current_user.id='{current_user.id}', user_id='{user_id}'.")
        abort(403)

    # ----------------------------------------------------------- #
    #  Validate user / Admin password
    # ----------------------------------------------------------- #
    if int(current_user.id) == int(user_id):
        # Validate against their own password
        if not user.validate_password(user, password, user_ip):
            app.logger.debug(f"delete_user(): Delete failed, incorrect password for user_id = '{user.id}'!")
            Event().log_event("Delete User Fail", f"Delete failed, incorrect password for user_id = '{user.id}'!")
            flash(f"Incorrect password for {user.name}.")
            return redirect(url_for('user_page', user_id=user_id))
    else:
        # Validate against current_user's (admins) password
        if not user.validate_password(current_user, password, user_ip):
            app.logger.debug(f"delete_user(): Delete failed, incorrect password for user_id = '{current_user.id}'!")
            Event().log_event("Delete User Fail", f"Incorrect password for user_id = '{current_user.id}'!")
            flash(f"Incorrect password for {current_user.name}.")
            return redirect(url_for('user_page', user_id=user_id))

    # ----------------------------------------------------------- #
    # Delete the user
    # ----------------------------------------------------------- #
    if User().delete_user(user_id):
        app.logger.debug(f"delete_user(): Success, user '{user.email}' deleted.")
        Event().log_event("Delete User Success", f"User '{user.email}' deleted.")
        flash(f"User '{user.name}' successfully deleted.")

        if current_user.admin \
                and int(current_user.id) != int(user_id):
            # Admin deleting someone, so back to admin
            return redirect(url_for('admin_page'))

        # ----------------------------------------------------------- #
        # User deleting themselves, so try and clean up
        # ----------------------------------------------------------- #
        # Log them out
        logout_user()

        # Clear the session
        session.clear()

        # Delete the user's "remember me" cookie as apparently logout doesn't do that
        # From: https://stackoverflow.com/questions/25144092/flask-login-still-logged-in-after-use-logouts-when-using-remember-me
        # This seems to work now....
        response = make_response(redirect(url_for('home')))
        response.delete_cookie(app.config['REMEMBER_COOKIE_NAME'])
        return response

    else:
        # Should never get here, but...
        app.logger.debug(f"delete_user(): User().delete_user() failed for user_id = '{user_id}'.")
        Event().log_event("Delete User Fail", f"User().delete_user() failed for user_id = '{user_id}'.")
        flash("Sorry, something went wrong.")
        return redirect(url_for('user_page', user_id=user_id))