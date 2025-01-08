from flask import url_for
from requests.auth import HTTPBasicAuth
from twilio.rest import Client
import requests
from unidecode import unidecode
from typing import Any


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, live_site, twilio_account_sid, twilio_auth_token, twilio_mobile_number


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.event_repository import EventRepository
from core.database.repositories.user_repository import UserModel, UserRepository, UNVERIFIED_PHONE_PREFIX, SUPER_ADMIN_USER_ID


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
def send_2fa_sms(user: UserModel) -> None:
    # ----------------------------------------------------------- #
    # Don't message from test site
    # ----------------------------------------------------------- #
    if not live_site():
        # Only message developer
        if user.id != SUPER_ADMIN_USER_ID:
            # Suppress SMS
            return

    # ----------------------------------------------------------- #
    # Send SMS via Twilio
    # ----------------------------------------------------------- #
    client = Client(twilio_account_sid, twilio_auth_token)
    message = client.messages.create(
        body=f"2FA URL: https://www.elsr.co.uk/{url_for('twofa_login')}?code={user.verification_code}"
             f"&email='{user.email}'  Code is {user.verification_code}",
        from_=twilio_mobile_number,
        to=user.phone_number
    )
    EventRepository().log_event("SMS", f"SMS 2FA sent to '{user.email}'. Status is '{message.status}'.")
    app.logger.debug(f"send_sms(): SMS 2FA sent to '{user.email}'. Status is '{message.status}'.")


# -------------------------------------------------------------------------------------------------------------- #
# Send SMS to verify phone number is correct
# -------------------------------------------------------------------------------------------------------------- #
def send_sms_verif_code(user: UserModel) -> None:
    # ----------------------------------------------------------- #
    # Don't message from test site
    # ----------------------------------------------------------- #
    if not live_site():
        # Only message developer
        if user.id != SUPER_ADMIN_USER_ID:
            # Suppress SMS
            return

    # ----------------------------------------------------------- #
    # Send SMS via Twilio
    # ----------------------------------------------------------- #
    client = Client(twilio_account_sid, twilio_auth_token)
    message = client.messages.create(
        body=f"Mobile verification URL: https://www.elsr.co.uk{url_for('mobile_verify')}?code={user.verification_code}"
             f"&email='{user.email}'   Code is {user.verification_code}",
        from_=twilio_mobile_number,
        to=user.phone_number[len(UNVERIFIED_PHONE_PREFIX):len(user.phone_number)]
    )
    EventRepository().log_event("SMS", f"SMS code sent to '{user.email}'. Status is '{message.status}'.")
    app.logger.debug(f"send_sms(): SMS code sent to '{user.email}'. Status is '{message.status}'.")


# -------------------------------------------------------------------------------------------------------------- #
# Generic send SMS
# -------------------------------------------------------------------------------------------------------------- #
def send_sms(user: UserModel, body: str) -> None:
    # ----------------------------------------------------------- #
    # Don't message from test site
    # ----------------------------------------------------------- #
    if not live_site():
        # Only message developer
        if user.id != SUPER_ADMIN_USER_ID:
            # Suppress SMS
            return

    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    body = unidecode(body)

    # ----------------------------------------------------------- #
    # Send SMS via Twilio
    # ----------------------------------------------------------- #
    client = Client(twilio_account_sid, twilio_auth_token)
    message = client.messages.create(
        body=body,
        from_=twilio_mobile_number,
        to=user.phone_number
    )
    EventRepository().log_event("SMS", f"Sent SMS to '{user.email}'. Status is '{message.status}'.")
    app.logger.debug(f"send_sms(): Sent SMS to '{user.email}'. Status is '{message.status}'.")


# -------------------------------------------------------------------------------------------------------------- #
# Alert Admin
# -------------------------------------------------------------------------------------------------------------- #
def alert_admin_via_sms(from_user: UserModel, message: str) -> None:
    # ----------------------------------------------------------- #
    #   Loop over all Admins
    # ----------------------------------------------------------- #
    admins: list[UserModel] = UserRepository().all_admins()
    for admin in admins:
        # All admins should have a valid phone number...
        if admin.has_valid_phone_number:
            # ----------------------------------------------------------- #
            #   Send SMS
            # ----------------------------------------------------------- #
            send_sms(admin, f"ELSR Admin alert from '{from_user.name}': {message}")
        else:
            # Should never get here, but...
            EventRepository().log_event("SMS admin alert", f"Admin '{admin.email}' doesn't appear to have a valid mobile number.")
            app.logger.debug(f"alert_admin_sms(): Admin '{admin.email}' doesn't appear to have a valid mobile number.")


# -------------------------------------------------------------------------------------------------------------- #
# Get Twilio balance
# -------------------------------------------------------------------------------------------------------------- #
def get_twilio_balance() -> list[Any]:
    """
    Look up Twilio balance.
    :return:                    [Balance value, Balance currency]
    """
    url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Balance.json"
    auth = HTTPBasicAuth(twilio_account_sid, twilio_auth_token)
    response = requests.get(url=url, auth=auth)
    response.raise_for_status()
    return [float(response.json()['balance']), response.json()['currency']]
