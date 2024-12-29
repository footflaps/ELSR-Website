from flask import render_template, redirect, url_for, flash, request, abort, session, make_response
from flask_login import login_user, current_user, logout_user
from threading import Thread
import os
from urllib.parse import urlparse


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.db_users import User, update_last_seen
from core.forms.user_forms import LoginUserForm, ResetPasswordForm
from core.database.repositories.db_events import Event
from core.subs_email_sms import send_reset_email, send_verification_email, send_2fa_sms


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
            return render_template("user_login.html", form=form, year=current_year, live_site=live_site())

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
            return render_template("user_login.html", form=form, year=current_year, live_site=live_site())

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
            return render_template("user_login.html", form=form, year=current_year, live_site=live_site())

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
            return render_template("user_login.html", form=form, year=current_year, live_site=live_site())

    # ------------------------------------------------------------------------------------------------- #
    #   GET - Show login page                                                                           #
    # ------------------------------------------------------------------------------------------------- #

    # Our current domain
    good_referrer = 'https://{0}/'.format(request.host)

    # Cache the calling referring page, so we can return to that after a successful login
    if not same_origin(request.referrer, good_referrer) \
            or "validate_email" in str(request.referrer) \
            or "reset" in str(request.referrer) \
            or "/home" in str(request.referrer):
        # If they've come from validate email, no point bouncing them back once they've logged in,
        # so forward them to home instead. Likewise, if they came from another site, don't jump back after login.
        session['url'] = url_for('display_blog')
    else:
        session['url'] = request.referrer

    return render_template("user_login.html", form=form, year=current_year, live_site=live_site())


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
            return render_template("user_reset_password.html", form=form, year=current_year, live_site=live_site())

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

    return render_template("user_reset_password.html", form=form, year=current_year, live_site=live_site())

