from flask import url_for
import smtplib
import os
from twilio.rest import Client
from core.dB_events import Event
from core.db_users import User, UNVERIFIED_PHONE_PREFIX
import logging


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

admin_email = os.environ['ELSR_ADMIN_EMAIL']
admin_password = os.environ['ELSR_ADMIN_EMAIL_PASSWORD']
my_email = os.environ['ELSR_CONTACT_EMAIL']

# Twilio
twilio_account_sid = os.environ['ELSR_TWILIO_SID']
twilio_auth_token = os.environ['ELSR_TWILIO_TOKEN']
twilio_mobile_number = os.environ['ELSR_TWILIO_NUMBER']

VERIFICATION_BODY = "Dear [USER], \n\n" \
                    "This is a verification email from www.elsr.co.uk. \n\n" \
                    "Your verification code is [CODE]. \n" \
                    "It will expire in 24 hours.\n\n" \
                    "To verify your email address, either:\n\n" \
                    "     1. Goto https://www.elsr.co.uk/validate_email and enter your code manually, or \n\n" \
                    "     2. Click on: https://www.elsr.co.uk/validate_email?code=[CODE]&email='[EMAIL]' \n\n" \
                    "If you were not expecting this email and have not visited www.elsr.co.uk, then don't worry, " \
                    "somebody probably made a typo when entering their email address and accidentally entered this " \
                    "one. Just delete this email and forget about it. Without access to this email account they can't " \
                    "continue and will eventually figure out they miss-typed their email address.\n\n" \
                    "Thanks, \n\n" \
                    "The Admin Team\n\n" \
                    "NB: Please do not reply to this email, the account is not monitored."

RESET_BODY = "Dear [USER], \n\n" \
             "This is a password rest email from www.elsr.co.uk. \n\n" \
             "Your reset code is [CODE]. \n" \
             "It will expire in 24 hours.\n\n" \
             "To reset your password, either:\n\n" \
             "     1. Goto https://www.elsr.co.uk/reset and enter your code manually, or \n\n" \
             "     2. Click on: https://www.elsr.co.uk/reset?code=[CODE]&email='[EMAIL]' \n\n" \
             "If you were not expecting this email and have not visited www.elsr.co.uk, then don't worry, " \
             "somebody probably made a typo when entering their email address and accidentally entered this " \
             "one. Just delete this email and forget about it. Without access to this email account they can't " \
             "continue and will eventually figure out they miss-typed their email address.\n\n" \
             "Thanks, \n\n" \
             "The Admin Team\n\n" \
             "NB: Please do not reply to this email, the account is not monitored."


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Email Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# Send an email
def send_verification_email(target_email, user_name, code):
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=admin_email, password=admin_password)
        subject = "Verification email."
        body = VERIFICATION_BODY.replace("[USER]", user_name)
        body = body.replace("[CODE]", str(code))
        body = body.replace("[EMAIL]", target_email)
        try:
            connection.sendmail(
                from_addr=admin_email,
                to_addrs=target_email,
                msg=f"To:{target_email}\nSubject:{subject}\n\n{body}"
            )
            logging.getLogger(__name__).debug(f"Email(): sent verification email to '{target_email}'")
            app.logger.debug(f"Email(): sent verification email to '{target_email}'")
            return True
        except Exception as e:
            logging.getLogger(__name__).debug(f"Email(): Failed to send verification email to '{target_email}', "
                                              f"error code was '{e.args}'.")
            app.logger.debug(
                f"Email(): Failed to send verification email to '{target_email}', error code was '{e.args}'.")
            return False


def send_reset_email(target_email, user_name, code):
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=admin_email, password=admin_password)
        subject = "Password reset email."
        body = RESET_BODY.replace("[USER]", user_name)
        body = body.replace("[CODE]", str(code))
        body = body.replace("[EMAIL]", target_email)
        try:
            connection.sendmail(
                from_addr=admin_email,
                to_addrs=target_email,
                msg=f"To:{target_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug("Email(): sent reset email to '{target_email}'")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send reset email to '{target_email}', error code was '{e.args}'.")
            return False


def contact_form_email(from_name, from_email, body):
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=admin_email, password=admin_password)
        subject = f"Message from elsr.co.uk from '{from_name}' ({from_email})"
        try:
            connection.sendmail(
                from_addr=admin_email,
                to_addrs=my_email,
                msg=f"To:{my_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Email(): sent message to '{my_email}'")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send message to '{my_email}', error code was '{e.args}'.")
            return False


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# SMS Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Send SMS for Two Factor Authentication
# -------------------------------------------------------------------------------------------------------------- #
def send_2fa_sms(user):
    client = Client(twilio_account_sid, twilio_auth_token)
    message = client.messages.create(
        body=f"2FA URL: https://www.elsr.co.uk/{url_for('twofa_login')}?code={user.verification_code}"
             f"&email='{user.email}'  Code is {user.verification_code}",
        from_=twilio_mobile_number,
        to=user.phone_number
    )
    Event().log_event("SMS", f"SMS 2FA sent to user_id = '{user.id}'. Status is '{message.status}'.")
    app.logger.debug(f"send_sms(): SMS 2FA sent to user_id = '{user.id}'. Status is '{message.status}'.")


# -------------------------------------------------------------------------------------------------------------- #
# Send SMS to verify phone number is correct
# -------------------------------------------------------------------------------------------------------------- #
def send_sms_verif_code(user):
    client = Client(twilio_account_sid, twilio_auth_token)
    message = client.messages.create(
        body=f"Mobile verification URL: https://www.elsr.co.uk{url_for('mobile_verify')}?code={user.verification_code}"
             f"&email='{user.email}'   Code is {user.verification_code}",
        from_=twilio_mobile_number,
        to=user.phone_number[len(UNVERIFIED_PHONE_PREFIX):len(user.phone_number)]
    )
    Event().log_event("SMS", f"SMS code sent to user_id = '{user.id}'. Status is '{message.status}'.")
    app.logger.debug(f"send_sms(): SMS code sent to user_id = '{user.id}'. Status is '{message.status}'.")


# -------------------------------------------------------------------------------------------------------------- #
# Generic send SMS
# -------------------------------------------------------------------------------------------------------------- #
def send_sms(user, message):
    client = Client(twilio_account_sid, twilio_auth_token)
    message = client.messages.create(
        body=message,
        from_=twilio_mobile_number,
        to=user.phone_number
    )
    Event().log_event("SMS", f"Sent SMS to '{user.id}'. Status is '{message.status}'.")
    app.logger.debug(f"send_sms(): Sent SMS to '{user.id}'. Status is '{message.status}'.")


# -------------------------------------------------------------------------------------------------------------- #
# Alert Admin
# -------------------------------------------------------------------------------------------------------------- #
def alert_admin_via_sms(from_user: User, message: str):
    admins = User().all_admins()
    for admin in admins:
        # All admins should have a valid phone number...
        if admin.has_valid_phone_number():
            send_sms(admin, f"ELSR Admin alert from '{from_user.name}': {message}")
        else:
            # Should never get here, but..
            Event().log_event("SMS admin alert", f"Admin '{admin.email}' doesn't appear to have a valid mobile number.")
            app.logger.debug(f"alert_admin_sms(): Admin '{admin.email}' doesn't appear to have a valid mobile number.")

