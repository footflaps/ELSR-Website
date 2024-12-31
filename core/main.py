from sqlalchemy import func
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db, app


# -------------------------------------------------------------------------------------------------------------- #
# Import our Models
# -------------------------------------------------------------------------------------------------------------- #

from core.database.models.user_model import UserModel
from core.database.models.cafe_model import CafeModel
from core.database.models.gpx_model import GpxModel
from core.database.models.calendar_model import CalendarModel
from core.database.models.social_model import SocialModel
from core.database.models.classified_model import ClassifiedModel
from core.database.models.message_model import MessageModel
from core.database.models.cafe_comment_model import CafeCommentModel
from core.database.models.event_model import EventModel
from core.database.models.poll_model import PollModel
from core.database.models.blog_model import BlogModel


# -------------------------------------------------------------------------------------------------------------- #
# Import the other route pages
# -------------------------------------------------------------------------------------------------------------- #

from core.routes.routes_admin import admin_page
from core.routes.routes_admin_maps import enable_maps
from core.routes.routes_blog import display_blog
from core.routes.routes_cafes import cafe_list
from core.routes.routes_calendar import calendar
from core.routes.routes_classifieds import classifieds
from core.routes.routes_errors import page_not_found
from core.routes.routes_events import delete_event
from core.routes.routes_gpx import gpx_details
from core.routes.routes_gpx_edit import edit_route
from core.routes.routes_gravel import gravel
from core.routes.routes_messages import mark_read
from core.routes.routes_polling import add_poll
from core.routes.routes_polling_voting import swap_vote
from core.routes.routes_social_signup import social_cant
from core.routes.routes_user_login_logout import login
from core.routes.routes_user_register import register
from core.routes.routes_users import user_page
from core.routes.routes_weekend import weekend
from core.routes.routes_socials import social
from core.routes.routes_club_kit import club_kit
from core.routes.routes_chaingang import chaingang
from core.routes.routes_tim_williams import twr
from core.routes.routes_elsr import contact
from core.routes.routes_ride_history import ride_history
from core.routes.routes_add_ride_to_calendar import add_ride


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():

    num_users = db.session.query(func.count(UserModel.id)).scalar()
    print(f"Found {num_users} users in the dB")

    num_cafes = db.session.query(func.count(CafeModel.id)).scalar()
    print(f"Found {num_cafes} cafes in the dB")

    num_gpx = db.session.query(func.count(GpxModel.id)).scalar()
    print(f"Found {num_gpx} gpx in the dB")

    num_calendar = db.session.query(func.count(CalendarModel.id)).scalar()
    print(f"Found {num_calendar} calendar entries in the dB")

    num_socials = db.session.query(func.count(SocialModel.id)).scalar()
    print(f"Found {num_socials} socials in the dB")

    num_classifieds = db.session.query(func.count(ClassifiedModel.id)).scalar()
    print(f"Found {num_classifieds} classifieds in the dB")

    num_messages = db.session.query(func.count(MessageModel.id)).scalar()
    print(f"Found {num_messages} messages in the dB")

    num_cafe_comments = db.session.query(func.count(CafeCommentModel.id)).scalar()
    print(f"Found {num_cafe_comments} cafe comments in the dB")

    num_events = db.session.query(func.count(EventModel.id)).scalar()
    print(f"Found {num_events} events in the dB")

    num_polls = db.session.query(func.count(PollModel.id)).scalar()
    print(f"Found {num_polls} polls in the dB")

    num_blogs = db.session.query(func.count(BlogModel.id)).scalar()
    print(f"Found {num_blogs} blogs in the dB")


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Main
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

if __name__ == "__main__":
    if os.path.exists("/home/ben_freeman_eu/elsr_website/ELSR-Website/env_vars.py"):
        app.run(debug=False)
    else:
        app.run(debug=False)
