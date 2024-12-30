from flask import url_for
import smtplib
import os
from requests.auth import HTTPBasicAuth
from twilio.rest import Client
import requests
from unidecode import unidecode
from datetime import datetime
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.event_repository import EventRepository
from core.database.repositories.db_users import User, UNVERIFIED_PHONE_PREFIX, MESSAGE_NOTIFICATION, GROUP_NOTIFICATIONS, \
                          SOCIAL_NOTIFICATION, BLOG_NOTIFICATION, SUPER_ADMIN_USER_ID
from core.database.repositories.message_repository import MessageRepository, ADMIN_EMAIL
from core.database.repositories.calendar_repository import CalendarRepository, GROUP_CHOICES, DEFAULT_START_TIMES
from core.database.repositories.social_repository import SocialRepository
from core.database.repositories.blog_repository import BlogRepository as Blog, Privacy
from core.database.repositories.gpx_repository import GpxRepository

from core.database.jinja.calendar_jinja import start_time_string, beautify_date
from core.database.jinja.user_jinja import get_user_name


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

RIDE_BODY = "Dear [USER], \n\n" \
            "A new [GROUP] ride has been posted to the Calendar for [DATE] by member [POSTER].\n" \
            "The ride start details are: [START]\n" \
            "The ride destination is: [DESTINATION]\n" \
            "The ride is [DISTANCE] km long and there is approx. [ASCENT] m climbing.\n" \
            "The route direction is: [DIRECTION]\n" \
            "The cafe is at: [CAFE_DISTANCE]\n" \
            "Here are some useful links:\n\n" \
            "See the calendar here: [CAL_LINK]\n" \
            "See details of the route here: [GPX_LINK]\n" \
            "Download the GPX file here: [DL_LINK]\n\n" \
            "Thanks, \n\n" \
            "The Admin Team\n\n" \
            "NB: Please do not reply to this email, the account is not monitored.\n" \
            "You received this email because you have subscribed to email notifications for [GROUP] rides.\n" \
            "You can disable this option from your user account page here: [ACCOUNT_LINK] \n\n" \
            "One click unsubscribe from ALL email notifications link: [UNSUBSCRIBE]\n"

SOCIAL_BODY = "Dear [USER], \n\n" \
              "A new social event has appeared on the website.\n" \
              "The date of the social is [DATE] and the location will be [LOCATION].\n" \
              "Here are some useful links:\n\n" \
              "See the calendar here: [CAL_LINK]\n" \
              "See the social event details here: [SOCIAL_LINK]\n\n" \
              "Thanks, \n\n" \
              "The Admin Team\n\n" \
              "NB: Please do not reply to this email, the account is not monitored.\n" \
              "You received this email because you have subscribed to email notifications for social events.\n" \
              "You can disable this option from your user account page here: [ACCOUNT_LINK] \n\n" \
              "One click unsubscribe from ALL email notifications link: [UNSUBSCRIBE]\n"

BLOG_BODY = "Dear [USER], \n\n" \
            "A new blog post has appeared on the website, from user '[BLOG_AUTHOR]'.\n" \
            "The subject of the blog post is '[BLOG_TITLE]'.\n" \
            "Here are some useful links:\n\n" \
            "See the blog page here: [BLOGS_LINK]\n" \
            "See this particular blog post here: [THIS_LINK]\n\n" \
            "Thanks, \n\n" \
            "The Admin Team\n\n" \
            "NB: Please do not reply to this email, the account is not monitored.\n" \
            "You received this email because you have subscribed to email notifications for social events.\n" \
            "You can disable this option from your user account page here: [ACCOUNT_LINK] \n\n" \
            "One click unsubscribe from ALL email notifications link: [UNSUBSCRIBE]\n"

CLASSIFIED_BODY = "Dear [USER], \n\n" \
                  "You have a message about your classified post [TITLE].\n" \
                  "The message is from [BUYER_NAME].\n" \
                  "Their email is [BUYER_EMAIL].\n" \
                  "Their mobile number is [BUYER_MOBILE].\n" \
                  "Their message is '[BUYER_MESSAGE]'\n\n" \
                  "Here are some useful links:\n\n" \
                  "See your classified post here: [CLASSIFIED_LINK]\n" \
                  "You can see all your classified posts from your user account page here: [ACCOUNT_LINK] \n\n" \
                  "Thanks, \n" \
                  "The Admin Team\n\n" \
                  "NB 1: Please do not reply to this email, the account is not monitored.\n" \
                  "NB 2: You received this email because you agreed to email messages when you posted your classified " \
                  "advert. To stop messages being forwarded to you, either mark your post as Sold or delete it from " \
                  "the website.\n"


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Email Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Send Blog notifications
# -------------------------------------------------------------------------------------------------------------- #

def send_blog_notification_emails(blog: Blog()):
    # ----------------------------------------------------------- #
    # Make sure social exists
    # ----------------------------------------------------------- #
    if not blog:
        app.logger.debug(f"send_blog_notification_emails(): Passed invalid blog object")
        EventRepository().log_event("send_blog_notification_emails() Fail", f"Passed invalid blog object")
        return

    # ----------------------------------------------------------- #
    # Scan all users
    # ----------------------------------------------------------- #
    for user in User().all_users():
        if user.notification_choice(BLOG_NOTIFICATION):
            # Users without write permissions can't see private blog posts
            if blog.private == Privacy.PUBLIC \
                    or user.readwrite():
                # ----------------------------------------------------------- #
                # Send email
                # ----------------------------------------------------------- #
                send_one_blog_notification_email(user, blog)


def send_one_blog_notification_email(user: User(), blog: Blog()):
    # ----------------------------------------------------------- #
    # Make sure user and ride exist
    # ----------------------------------------------------------- #
    if not user:
        app.logger.debug(f"send_one_blog_notification_email(): Passed invalid user object")
        EventRepository().log_event("send_one_blog_notification_email() Fail", f"Passed invalid user object")
        return
    if not blog:
        app.logger.debug(f"send_one_blog_notification_email(): Passed invalid blog object")
        EventRepository().log_event("send_one_blog_notification_email() Fail", f"Passed invalid blog object")
        return

    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    target_email = unidecode(user.email)
    user_name = unidecode(user.name)
    blog_title = unidecode(blog.title)
    blog_author = unidecode(get_user_name(blog.email))

    # ----------------------------------------------------------- #
    # Create hyperlinks
    # ----------------------------------------------------------- #
    blogs_link = f"https://www.elsr.co.uk/blog"
    this_link = f"https://www.elsr.co.uk/blog?blog_id={blog.id}"
    user_page = f"https://www.elsr.co.uk/user_page?user_id={user.id}&anchor=account"
    one_click_unsubscribe = f"https://www.elsr.co.uk/unsubscribe_all?email={user.email}&code={user.unsubscribe_code()}"

    # ----------------------------------------------------------- #
    # Don't message from test site
    # ----------------------------------------------------------- #
    if not live_site():
        # Only message developer
        if user.id != SUPER_ADMIN_USER_ID:
            # Suppress SMS
            return

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = f"ELSR: New blog post notification"
        body = BLOG_BODY.replace("[USER]", user_name)
        body = body.replace("[BLOG_AUTHOR]", blog_author)
        body = body.replace("[BLOG_TITLE]", blog_title)
        body = body.replace("[BLOGS_LINK]", blogs_link)
        body = body.replace("[THIS_LINK]", this_link)
        body = body.replace("[ACCOUNT_LINK]", user_page)
        body = body.replace("[UNSUBSCRIBE]", one_click_unsubscribe)

        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=target_email,
                msg=f"To:{target_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Email(): sent message email to '{target_email}'")
            EventRepository().log_event("Email Success", f"Sent message email to '{target_email}'.")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send message email to '{target_email}', error code was '{e.args}'.")
            EventRepository().log_event("Email Fail", f"Failed to send message email to '{target_email}', "
                                            f"error code was '{e.args}'.")
            return False


# user = User().find_user_from_id(1)
# blog = Blog().find_blog_from_id(1)
# send_one_blog_notification_email(user, blog)


# -------------------------------------------------------------------------------------------------------------- #
# Send Social notifications
# -------------------------------------------------------------------------------------------------------------- #

def send_social_notification_emails(social: SocialRepository()):
    # ----------------------------------------------------------- #
    # Make sure social exists
    # ----------------------------------------------------------- #
    if not social:
        app.logger.debug(f"send_social_notification_emails(): Passed invalid social object")
        EventRepository().log_event("send_social_notification_emails() Fail", f"Passed invalid social object")
        return

    # ----------------------------------------------------------- #
    # Scan all users
    # ----------------------------------------------------------- #
    for user in User().all_users():
        if user.notification_choice(SOCIAL_NOTIFICATION):
            # ----------------------------------------------------------- #
            # Send email
            # ----------------------------------------------------------- #
            send_one_social_notification_email(user, social)


def send_one_social_notification_email(user: User(), social: SocialRepository()):
    # ----------------------------------------------------------- #
    # Make sure user and ride exist
    # ----------------------------------------------------------- #
    if not user:
        app.logger.debug(f"send_one_social_notification_email(): Passed invalid user object")
        EventRepository().log_event("send_one_social_notification_email() Fail", f"Passed invalid user object")
        return
    if not social:
        app.logger.debug(f"send_one_social_notification_email(): Passed invalid social object")
        EventRepository().log_event("send_one_social_notification_email() Fail", f"Passed invalid social object")
        return

    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    target_email = unidecode(user.email)
    user_name = unidecode(user.name)
    destination = unidecode(social.destination)
    date = beautify_date(social.date)

    # ----------------------------------------------------------- #
    # Create hyperlinks
    # ----------------------------------------------------------- #
    cal_link = f"https://www.elsr.co.uk/calendar?date={date}"
    social_link = f"https://www.elsr.co.uk/social?date={date}"
    user_page = f"https://www.elsr.co.uk/user_page?user_id={user.id}&anchor=account"
    one_click_unsubscribe = f"https://www.elsr.co.uk/unsubscribe_all?email={user.email}&code={user.unsubscribe_code()}"

    # ----------------------------------------------------------- #
    # Don't message from test site
    # ----------------------------------------------------------- #
    if not live_site():
        # Only message developer
        if user.id != SUPER_ADMIN_USER_ID:
            # Suppress SMS
            return

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = f"ELSR: New social event notification"
        body = SOCIAL_BODY.replace("[USER]", user_name)
        # NB The social
        body = body.replace("[DATE]", date.replace("/", ""))
        body = body.replace("[LOCATION]", destination)
        body = body.replace("[CAL_LINK]", cal_link)
        body = body.replace("[SOCIAL_LINK]", social_link)
        body = body.replace("[ACCOUNT_LINK]", user_page)
        body = body.replace("[UNSUBSCRIBE]", one_click_unsubscribe)

        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=target_email,
                msg=f"To:{target_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Email(): sent message email to '{target_email}'")
            EventRepository().log_event("Email Success", f"Sent message email to '{target_email}'.")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send message email to '{target_email}', error code was '{e.args}'.")
            EventRepository().log_event("Email Fail", f"Failed to send message email to '{target_email}', "
                                            f"error code was '{e.args}'.")
            return False

# user = User().find_user_from_id(1)
# social = Socials().one_social_id(1)
# send_one_social_notification_email(user, social)


# -------------------------------------------------------------------------------------------------------------- #
# Send ride notifications
# -------------------------------------------------------------------------------------------------------------- #

def send_ride_notification_emails(ride: CalendarRepository()):
    # ----------------------------------------------------------- #
    # Make sure ride exists
    # ----------------------------------------------------------- #
    if not ride:
        # Should never happen, but...
        app.logger.debug(f"send_ride_notification_emails(): Passed invalid ride object")
        EventRepository().log_event("send_ride_notification_emails() Fail", f"Passed invalid ride object")
        return

    # ----------------------------------------------------------- #
    # Make sure the GPX exists
    # ----------------------------------------------------------- #
    gpx = GpxRepository().one_gpx(ride.gpx_id)
    if not gpx:
        # Should never happen, but...
        app.logger.debug(f"send_ride_notification_emails(): Can't find GPX, ride.id = '{ride.id}', "
                         f"ride.gpx_id = '{ride.gpx_id}'.")
        EventRepository().log_event("send_ride_notification_emails() Fail", f"Can't find GPX, ride.id = '{ride.id}', "
                                                                  f"ride.gpx_id = '{ride.gpx_id}'.")
        return

    # ----------------------------------------------------------- #
    # Make sure the GPX file is public
    # ----------------------------------------------------------- #
    if not gpx.public:
        # Should never happen, but...
        app.logger.debug(f"send_ride_notification_emails(): Aborting as GPX not public, ride.id = '{ride.id}', "
                         f"ride.gpx_id = '{ride.gpx_id}'.")
        EventRepository().log_event("send_ride_notification_emails() Fail", f"Aborting as GPX not public, ride.id = '{ride.id}', "
                                                                  f"ride.gpx_id = '{ride.gpx_id}'.")
        return

    # ----------------------------------------------------------- #
    # Abort if we've already sent an email alert
    # ----------------------------------------------------------- #
    if ride.sent_email == "True":
        # Should never happen, but...
        app.logger.debug(f"send_ride_notification_emails(): Aborting as already sent email, ride.id = '{ride.id}'.")
        EventRepository().log_event("send_ride_notification_emails() Fail", f"Aborting as already sent email, "
                                                                  f"ride.id = '{ride.id}'.")
        return

    # ----------------------------------------------------------- #
    # Modify ride to show email have been sent
    # ----------------------------------------------------------- #
    # Do this now in case we crash mid-email send
    CalendarRepository().mark_email_sent(ride.id)

    # ----------------------------------------------------------- #
    # Scan all users
    # ----------------------------------------------------------- #
    for user in User().all_users():
        # Match group, slightly complex as we use different strings in the ride object and the user object
        # GROUP_CHOICES is the set used by Calendar() (of which ride in an instantiation)
        # GROUP_NOTIFICATIONS is the set used by User()
        for choice, notification in zip(GROUP_CHOICES, GROUP_NOTIFICATIONS):
            # Match both the ride and the user's email preference
            if ride.group == choice and \
                    user.notification_choice(notification):

                # ----------------------------------------------------------- #
                # Send email
                # ----------------------------------------------------------- #
                send_one_ride_notification_email(user, ride)


def send_one_ride_notification_email(user: User(), ride: CalendarRepository()):
    # ----------------------------------------------------------- #
    # Make sure user and ride exist
    # ----------------------------------------------------------- #
    if not user:
        app.logger.debug(f"send_one_ride_notification_email(): Passed invalid user object")
        EventRepository().log_event("send_one_ride_notification_email() Fail", f"Passed invalid user object")
        return
    if not ride:
        app.logger.debug(f"send_one_ride_notification_email(): Passed invalid ride object")
        EventRepository().log_event("send_one_ride_notification_email() Fail", f"Passed invalid ride object")
        return

    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    target_email = unidecode(user.email)
    user_name = unidecode(user.name)
    group = ride.group
    date = beautify_date(ride.date)
    leader = unidecode(ride.leader)
    if ride.start_time:
        start = unidecode(ride.start_time)
    else:
        date_obj = datetime(int(date[4:8]), int(date[2:4]), int(date[0:2]), 0, 00)
        day = date_obj.strftime('%A')
        start = unidecode(start_time_string(DEFAULT_START_TIMES[day]))
    destination = unidecode(ride.destination)

    # ----------------------------------------------------------- #
    # Get GPX / Direction
    # ----------------------------------------------------------- #
    gpx = GpxRepository().one_gpx(ride.gpx_id)
    direction = "n/a"
    if gpx:
        if gpx.direction == "CW":
            direction = "Clockwise"
        elif gpx.direction == "CCW":
            direction = "Anti-clockwise"

    # ----------------------------------------------------------- #
    # Distance to cafe
    # ----------------------------------------------------------- #
    cafe_distance = "unknown"
    ascent = "unknown"
    distance = "unknown"
    if gpx:
        ascent = str(gpx.ascent_m)
        distance = str(gpx.length_km)
        for cafe_passed in json.loads(gpx.cafes_passed):
            if cafe_passed["cafe_id"] == ride.cafe_id:
                km = cafe_passed["range_km"]
                cafe_distance = f"{km} km / {round(km/1.6,1)} miles"
                break

    # ----------------------------------------------------------- #
    # Create hyperlinks
    # ----------------------------------------------------------- #
    cal_link = f"https://www.elsr.co.uk/weekend?date={ride.date}"
    gpx_link = f"https://www.elsr.co.uk/route/{ride.gpx_id}"
    dl_link = f"https://www.elsr.co.uk//gpx_download2?email={user.email}&gpx_id={ride.gpx_id}&" \
              f"code={user.gpx_download_code(ride.gpx_id)}"
    user_page = f"https://www.elsr.co.uk/user_page?user_id={user.id}&anchor=account"
    one_click_unsubscribe = f"https://www.elsr.co.uk/unsubscribe_all?email={user.email}&code={user.unsubscribe_code()}"

    # ----------------------------------------------------------- #
    # Don't message from test site
    # ----------------------------------------------------------- #
    if not live_site():
        # Only message developer
        if user.id != SUPER_ADMIN_USER_ID:
            # Suppress SMS
            return

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = f"ELSR: New {group} ride notification"
        body = RIDE_BODY.replace("[USER]", user_name)
        body = body.replace("[GROUP]", group)
        body = body.replace("[DATE]", date)
        body = body.replace("[POSTER]", leader)
        body = body.replace("[START]", start)
        body = body.replace("[DESTINATION]", destination)
        body = body.replace("[ASCENT]", ascent)
        body = body.replace("[DISTANCE]", distance)
        body = body.replace("[DIRECTION]", direction)
        body = body.replace("[CAFE_DISTANCE]", cafe_distance)
        body = body.replace("[CAL_LINK]", cal_link)
        body = body.replace("[DL_LINK]", dl_link)
        body = body.replace("[GPX_LINK]", gpx_link)
        body = body.replace("[ACCOUNT_LINK]", user_page)
        body = body.replace("[UNSUBSCRIBE]", one_click_unsubscribe)

        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=target_email,
                msg=f"To:{target_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Email(): sent message email to '{target_email}'")
            EventRepository().log_event("Email Success", f"Sent message email to '{target_email}'.")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send message email to '{target_email}', error code was '{e.args}'.")
            EventRepository().log_event("Email Fail", f"Failed to send message email to '{target_email}', "
                                            f"error code was '{e.args}'.")
            return False

# user = User().find_user_from_id(1)
# ride = Calendar().one_ride_id(1)
# send_one_ride_notification_email(user, ride)

# for group in GROUP_CHOICES:
#     ride = Calendar(group=group)
#     print(f"Testing ride {ride.group}")
#     send_ride_notification_emails(ride)


# -------------------------------------------------------------------------------------------------------------- #
# Send email notification for message to user
# -------------------------------------------------------------------------------------------------------------- #

def send_message_notification_email(message: MessageRepository(), user: User()):
    # ----------------------------------------------------------- #
    # Make sure user and message exist
    # ----------------------------------------------------------- #
    if not user:
        app.logger.debug(f"send_message_notification_email(): Passed invalid user object")
        EventRepository().log_event("send_message_notification_email() Fail", f"Passed invalid user object")
        return
    if not message:
        app.logger.debug(f"send_message_notification_email(): Passed invalid message object")
        EventRepository().log_event("send_message_notification_email() Fail", f"Passed invalid message object")
        return

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
    one_click_unsubscribe = f"https://www.elsr.co.uk/unsubscribe_all?email={user.email}&code={user.unsubscribe_code()}"

    # ----------------------------------------------------------- #
    # Don't message from test site
    # ----------------------------------------------------------- #
    if not live_site():
        # Only message developer
        if user.id != SUPER_ADMIN_USER_ID:
            # Suppress SMS
            return

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = f"ELSR: Message notification from '{from_name}'"
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
            EventRepository().log_event("Email Success", f"Sent message email to '{target_email}'.")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send message email to '{target_email}', error code was '{e.args}'.")
            EventRepository().log_event("Email Fail", f"Failed to send message email to '{target_email}', "
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
# Send message to classified seller
# -------------------------------------------------------------------------------------------------------------- #
def send_message_to_seller(classified, buyer_name, buyer_email, buyer_mobile, buyer_message):
    # ----------------------------------------------------------- #
    # Find user
    # ----------------------------------------------------------- #
    user = User().find_user_from_email(classified.email)
    if not user:
        app.logger.debug(f"send_message_to_seller(): Can't locate user from email = '{classified.email}'.")
        EventRepository().log_event("send_message_to_seller() Fail", f"Can't locate user from email = '{classified.email}'.")
        return

    # ----------------------------------------------------------- #
    # Strip out any non ascii chars
    # ----------------------------------------------------------- #
    buyer_name = unidecode(buyer_name)
    buyer_email = unidecode(buyer_email)
    buyer_mobile = unidecode(buyer_mobile)
    buyer_message = unidecode(buyer_message)
    classified_link = f"https://www.elsr.co.uk/classifieds?classified_id={classified.id}"
    user_page = f"https://www.elsr.co.uk/user_page?user_id={user.id}"

    # ----------------------------------------------------------- #
    # Construct the email
    # ----------------------------------------------------------- #
    subject = f"ELSR: Classified Message for {classified.title}!"

    body = CLASSIFIED_BODY.replace("[USER]", get_user_name(classified.email))
    body = body.replace("[TITLE]", classified.title)
    body = body.replace("[BUYER_NAME]", buyer_name)
    body = body.replace("[BUYER_EMAIL]", buyer_email)
    body = body.replace("[BUYER_MOBILE]", buyer_mobile)
    body = body.replace("[BUYER_MESSAGE]", buyer_message)
    body = body.replace("[CLASSIFIED_LINK]", classified_link)
    body = body.replace("[ACCOUNT_LINK]", user_page)

    # ----------------------------------------------------------- #
    # Don't message from test site
    # ----------------------------------------------------------- #
    if not live_site():
        # Only message developer
        if user.id != SUPER_ADMIN_USER_ID:
            # Suppress SMS
            return

    # ----------------------------------------------------------- #
    # Send the email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=classified.email,
                msg=f"To:{classified.email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Alert Email(): sent message to '{brf_personal_email}'.")
            EventRepository().log_event("Alert Email Success", f"Sent message to '{brf_personal_email}'")
            return True
        except Exception as e:
            app.logger.debug(
                f"Alert Email(): Failed to send message to '{brf_personal_email}', error code was '{e.args}'.")
            EventRepository().log_event("Alert Email Fail", f"Failed to send message to '{brf_personal_email}', "
                                                  f"error code was '{e.args}'.")
            return False


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
    # Don't message from test site
    # ----------------------------------------------------------- #
    if not live_site():
        return

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = "ELSR: Verification email."
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
            EventRepository().log_event("Email Success", f"Sent verification email to '{target_email}'.")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send verification email to '{target_email}', error code was '{e.args}'.")
            EventRepository().log_event("Email Fail", f"Failed to send verification email to '{target_email}', "
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
    # Don't message from test site
    # ----------------------------------------------------------- #
    if not live_site():
        return

    # ----------------------------------------------------------- #
    # Send an email
    # ----------------------------------------------------------- #
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
        connection.login(user=gmail_admin_acc_email, password=gmail_admin_acc_password)
        subject = "ELSR: Password reset email."
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
            EventRepository().log_event("Email Success", f"Sent reset email to '{target_email}'.")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send reset email to '{target_email}', error code was '{e.args}'.")
            EventRepository().log_event("Email Fail", f"Failed to send reset email to '{target_email}', "
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
        subject = f"ELSR: Message from '{from_name}' ({from_email})"
        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=brf_personal_email,
                msg=f"To:{brf_personal_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Email(): sent message to '{brf_personal_email}'.")
            EventRepository().log_event("Email Success", f"Sent message to '{brf_personal_email}'")
            return True
        except Exception as e:
            app.logger.debug(
                f"Email(): Failed to send message to '{brf_personal_email}', error code was '{e.args}'.")
            EventRepository().log_event("Email Fail", f"Failed to send message to '{brf_personal_email}', "
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
        subject = f"ELSR: Alert notification!"
        try:
            connection.sendmail(
                from_addr=gmail_admin_acc_email,
                to_addrs=brf_personal_email,
                msg=f"To:{brf_personal_email}\nSubject:{subject}\n\n{body}"
            )
            app.logger.debug(f"Alert Email(): sent message to '{brf_personal_email}'.")
            EventRepository().log_event("Alert Email Success", f"Sent message to '{brf_personal_email}'")
            return True
        except Exception as e:
            app.logger.debug(
                f"Alert Email(): Failed to send message to '{brf_personal_email}', error code was '{e.args}'.")
            EventRepository().log_event("Alert Email Fail", f"Failed to send message to '{brf_personal_email}', "
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
def send_sms_verif_code(user):
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
def send_sms(user, body):
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
    # Send SMS
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
            EventRepository().log_event("SMS admin alert", f"Admin '{admin.email}' doesn't appear to have a valid mobile number.")
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


# -------------------------------------------------------------------------------------------------------------- #
# Summarise who gets emails
# -------------------------------------------------------------------------------------------------------------- #
def email_ride_alert_summary():
    # Get all users
    users = User().all_users_sorted()
    # Scan by ride types
    results = {}
    one_words = GROUP_CHOICES + ["Socials", "Blogs", "Messages"]
    user_notifications = GROUP_NOTIFICATIONS + [SOCIAL_NOTIFICATION, BLOG_NOTIFICATION, MESSAGE_NOTIFICATION]
    for choice, notification in zip(one_words, user_notifications):
        alerted_users = []
        for user in users:
            if user.notification_choice(notification):
                alerted_users.append(user.email)
        results[choice] = alerted_users
    # Return our Dictionary
    return results


