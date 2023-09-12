from flask import url_for
import smtplib
import os
from requests.auth import HTTPBasicAuth
from twilio.rest import Client
import requests
from unidecode import unidecode


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app
from core.dB_events import Event
from core.db_users import User, UNVERIFIED_PHONE_PREFIX, MESSAGE_NOTIFICATION, get_user_name
from core.db_messages import Message, ADMIN_EMAIL


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

gmail_admin_acc_email = os.environ['ELSR_ADMIN_EMAIL']
gmail_admin_acc_password = os.environ['ELSR_ADMIN_EMAIL_PASSWORD']
brf_personal_email = os.environ['ELSR_CONTACT_EMAIL']

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

MESSAGE_BODY = "Dear [USER], \n\n" \
               "You have received a message from www.elsr.co.uk. \n\n" \
               "The message is from '[FROM]'.\n\n" \
               "The message is: \n\n" \
               "'[BODY]' \n\n" \
               "Thanks, \n\n" \
               "The Admin Team\n\n" \
               "NB: Please do not reply to this email, the account is not monitored.\n" \
               "You received this email because you have subscribed to email notifications for messages.\n" \
               "You can disable this option from your user account page here: [ACCOUNT_LINK] \n\n" \
               "One click unsubscribe from ALL email notifications link: [UNSUBSCRIBE]\n"


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Email Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Send email notification for message to user
# -------------------------------------------------------------------------------------------------------------- #

def send_message_notification_email(message, user):
    # ----------------------------------------------------------- #
    # Check user wants email alerts for messages
    # ----------------------------------------------------------- #
    if user == ADMIN_EMAIL:
        # Send email to admins not really supported
        print(f"Message to admins.... TBC")
        return
    elif not user.notification_choice(MESSAGE_NOTIFICATION):
        # Nope, so just return
        print(f"User '{user.email}' doesn't want email alerts for messages.")
        return
    else:
        print(f"User '{user.email}' does want email alerts for messages.")

    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    # message = Message().find_messages_by_id(message_id)
    target_email = unidecode(user.email)
    user_name = unidecode(user.name)
    content = unidecode(message.body)
    if message.from_email == ADMIN_EMAIL:
        from_name = "The Admin Team"
    else:
        from_name = unidecode(get_user_name(message.from_email))

    # ----------------------------------------------------------- #
    # Create hyperlinks
    # ----------------------------------------------------------- #
    user_page = f"https://www.elsr.co.uk/user_page?user_id={user.id}&anchor=account"
    one_click_unsubscribe = "TBD"

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = f"Message notification from {from_name}"
        body = MESSAGE_BODY.replace("[USER]", user_name)
        body = body.replace("[BODY]", content)
        body = body.replace("[FROM]", from_name)
        body = body.replace("[ACCOUNT_LINK]", user_page)
        body = body.replace("[UNSUBSCRIBE]", one_click_unsubscribe)

        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=target_email,
                msg=f"To:{target_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Email(): sent message email to '{target_email}'")
            Event().log_event("Email Success", f"Sent message email to '{target_email}'.")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send message email to '{target_email}', error code was '{e.args}'.")
            Event().log_event("Email Fail", f"Failed to send message email to '{target_email}', "
                                            f"error code was '{e.args}'.")
            return False


# user = User().find_user_from_id(1)
# print(f"user.notifications = '{user.notifications}'")
# message = Message(
#     from_email=ADMIN_EMAIL,
#     to_email="ben@freeman.net",
#     body=f"Hi Ben. from fred"
# )
# send_message_notification_email(message, user)



# -------------------------------------------------------------------------------------------------------------- #
# Send email verification code to new user
# -------------------------------------------------------------------------------------------------------------- #
def send_verification_email(target_email, user_name, code):
    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    target_email = unidecode(target_email)
    user_name = unidecode(user_name)

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = "Verification email."
        body = VERIFICATION_BODY.replace("[USER]", user_name)
        body = body.replace("[CODE]", str(code))
        body = body.replace("[EMAIL]", target_email)
        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=target_email,
                msg=f"To:{target_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Email(): sent verification email to '{target_email}'")
            Event().log_event("Email Success", f"Sent verification email to '{target_email}'.")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send verification email to '{target_email}', error code was '{e.args}'.")
            Event().log_event("Email Fail", f"Failed to send verification email to '{target_email}', "
                                            f"error code was '{e.args}'.")
            return False


# -------------------------------------------------------------------------------------------------------------- #
# Sent reset password code to user
# -------------------------------------------------------------------------------------------------------------- #
def send_reset_email(target_email, user_name, code):
    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    target_email = unidecode(target_email)
    user_name = unidecode(user_name)

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = "Password reset email."
        body = RESET_BODY.replace("[USER]", user_name)
        body = body.replace("[CODE]", str(code))
        body = body.replace("[EMAIL]", target_email)
        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=target_email,
                msg=f"To:{target_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Email(): sent reset email to '{target_email}'")
            Event().log_event("Email Success", f"Sent reset email to '{target_email}'.")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send reset email to '{target_email}', error code was '{e.args}'.")
            Event().log_event("Email Fail", f"Failed to send reset email to '{target_email}', "
                                            f"error code was '{e.args}'.")
            return False


# -------------------------------------------------------------------------------------------------------------- #
# Forward message from contact form onto site owner (BRF)
# -------------------------------------------------------------------------------------------------------------- #
def contact_form_email(from_name, from_email, body):
    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    from_name = unidecode(from_name)
    from_email = unidecode(from_email)
    body = unidecode(body)

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = f"Message from elsr.co.uk from '{from_name}' ({from_email})"
        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=brf_personal_email,
                msg=f"To:{brf_personal_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Email(): sent message to '{brf_personal_email}'.")
            Event().log_event("Email Success", f"Sent message to '{brf_personal_email}'")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send message to '{brf_personal_email}', error code was '{e.args}'.")
            Event().log_event("Email Fail", f"Failed to send message to '{brf_personal_email}', "
                                            f"error code was '{e.args}'.")
            return False


# -------------------------------------------------------------------------------------------------------------- #
# Internal system alerts to site owner (BRF)
# -------------------------------------------------------------------------------------------------------------- #
def send_system_alert_email(body):
    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    body = unidecode(body)

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = f"Alert from elsr.co.uk"
        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=brf_personal_email,
                msg=f"To:{brf_personal_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Alert Email(): sent message to '{brf_personal_email}'.")
            Event().log_event("Alert Email Success", f"Sent message to '{brf_personal_email}'")
            return True
        except Exception as e:
            app.logger.debug(
                f"Alert Email(): Failed to send message to '{brf_personal_email}', error code was '{e.args}'.")
            Event().log_event("Alert Email Fail", f"Failed to send message to '{brf_personal_email}', "
                                                  f"error code was '{e.args}'.")
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
    Event().log_event("SMS", f"SMS 2FA sent to '{user.email}'. Status is '{message.status}'.")
    app.logger.debug(f"send_sms(): SMS 2FA sent to '{user.email}'. Status is '{message.status}'.")


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
    Event().log_event("SMS", f"SMS code sent to '{user.email}'. Status is '{message.status}'.")
    app.logger.debug(f"send_sms(): SMS code sent to '{user.email}'. Status is '{message.status}'.")


# -------------------------------------------------------------------------------------------------------------- #
# Generic send SMS
# -------------------------------------------------------------------------------------------------------------- #
def send_sms(user, body):
    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    body = unidecode(body)

    # ----------------------------------------------------------- #
    # Send SMS
    # ----------------------------------------------------------- #
    client = Client(twilio_account_sid, twilio_auth_token)
    message = client.messages.create(
        body=body,
        from_=twilio_mobile_number,
        to=user.phone_number
    )
    Event().log_event("SMS", f"Sent SMS to '{user.email}'. Status is '{message.status}'.")
    app.logger.debug(f"send_sms(): Sent SMS to '{user.email}'. Status is '{message.status}'.")


# -------------------------------------------------------------------------------------------------------------- #
# Alert Admin
# -------------------------------------------------------------------------------------------------------------- #
def alert_admin_via_sms(from_user: User, message: str):
    # ----------------------------------------------------------- #
    #   Loop over all Admins
    # ----------------------------------------------------------- #
    admins = User().all_admins()
    for admin in admins:
        # All admins should have a valid phone number...
        if admin.has_valid_phone_number():
            # ----------------------------------------------------------- #
            #   Send SMS
            # ----------------------------------------------------------- #
            send_sms(admin, f"ELSR Admin alert from '{from_user.name}': {message}")
        else:
            # Should never get here, but..
            Event().log_event("SMS admin alert", f"Admin '{admin.email}' doesn't appear to have a valid mobile number.")
            app.logger.debug(f"alert_admin_sms(): Admin '{admin.email}' doesn't appear to have a valid mobile number.")


# -------------------------------------------------------------------------------------------------------------- #
# Get Twillio balance
# -------------------------------------------------------------------------------------------------------------- #
def get_twilio_balance():
    url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Balance.json"
    auth = HTTPBasicAuth(twilio_account_sid, twilio_auth_token)
    response = requests.get(url=url, auth=auth)
    response.raise_for_status()
    return [float(response.json()['balance']), response.json()['currency']]

