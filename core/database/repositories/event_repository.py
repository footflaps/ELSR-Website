from flask_login import current_user
from datetime import datetime
import time


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db
from core.database.models.events_model import EventModel


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

SECONDS_IN_DAY = 60 * 60 * 24

# Hack for converting 'all' to days (10 years will probably be enough)
ALL_DAYS = 365 * 10


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Event Repository Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class EventRepository(EventModel):

    # -------------------------------------------------------------------------------------------------------------- #
    # Create
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def add_event(event: EventModel) -> bool:
        # Time stamp the event bases on when we add to dB
        # NB Use Unix epoch time (rounded to an Int)
        event.date = int(time.time())

        # Try and add to dB
        with app.app_context():
            try:
                db.session.add(event)
                db.session.commit()
                # Return success
                return True

            except Exception as e:
                db.rollback()
                app.logger.error(f"dB.add_event(): Failed with error code '{e.args}'.")
                return False

    @staticmethod
    def log_event(event_type: int, event_details: str) -> bool:
        with app.app_context():
            # Can we get a user email address
            # If this is called from a Threaded task it won't necessarily have a valid
            # current_user and .is_authenticated won't exist
            try:
                if current_user.is_authenticated:
                    user_email = current_user.email
                else:
                    user_email = "not logged in"
            except AttributeError:
                user_email = "background"

            # Create a new event
            event = EventRepository(
                email=user_email,
                type=event_type,
                details=event_details,
                date=int(time.time())
            )

            # Add to events log
            try:
                db.session.add(event)
                db.session.commit()
                # Return success
                return True
            except Exception as e:
                db.rollback()
                app.logger.error(f"dB.log_event(): Failed with error code '{e.args}'.")
                return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Modify
    # -------------------------------------------------------------------------------------------------------------- #

    # -------------------------------------------------------------------------------------------------------------- #
    # Delete
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def delete_events_email_days(email: str, days: int) -> bool:
        if days == "all":
            days = ALL_DAYS
        timestamp = time.time() - SECONDS_IN_DAY * int(days)

        try:
            with app.app_context():
                events = EventModel.query.filter_by(email=email).filter(EventRepository.date > timestamp).all()
                for event in events:
                    db.session.delete(event)
                db.session.commit()
                return True

        except Exception as e:
            db.rollback()
            app.logger.error(f"dB.delete_events_email_days(): Failed with error code '{e.args}'.")
            return False

    @staticmethod
    def delete_events_all_days(days: int) -> bool:
        if days == "all":
            days = ALL_DAYS
        timestamp = time.time() - SECONDS_IN_DAY * int(days)
        try:
            with app.app_context():
                events = db.session.query(EventRepository).filter(EventRepository.date > timestamp).all()
                for event in events:
                    db.session.delete(event)
                db.session.commit()
                return True

        except Exception as e:
            db.rollback()
            app.logger.error(f"dB.delete_events_all_days(): Failed with error code '{e.args}'.")
            return False

    @staticmethod
    def delete_all_404s() -> bool:
        try:
            with app.app_context():
                events = db.session.query(EventRepository).filter_by(type="404").all()
                for event in events:
                    db.session.delete(event)
                db.session.commit()
                return True

        except Exception as e:
            db.rollback()
            app.logger.error(f"dB.delete_all_404s(): Failed with error code '{e.args}'.")
            return False

    @staticmethod
    def delete_event(event_id: int) -> bool:
        with app.app_context():
            event = db.session.query(EventRepository).filter_by(id=event_id).first()

            if event:
                try:
                    db.session.delete(event)
                    db.session.commit()
                    return True

                except Exception as e:
                    db.rollback()
                    app.logger.error(f"dB.delete_event(): Failed with error code '{e.args}'.")
                    return False
        app.logger.error(f"dB.delete_event(): Failed to delete event.id = {event_id}, event not found.")
        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Search
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def all_events() -> list[EventModel]:
        with app.app_context():
            events = EventModel.query.all()
            return events

    @staticmethod
    def event_id(id: int) -> EventModel | None:
        with app.app_context():
            event = EventModel.query.filter_by(id=id).first()
            return event

    @staticmethod
    def all_events_days(days: int) -> list[EventModel]:
        if days == "all":
            days = ALL_DAYS
        timestamp = time.time() - SECONDS_IN_DAY * int(days)
        with app.app_context():
            events = EventModel.query.filter(EventRepository.date > timestamp).all()
            return events

    @staticmethod
    def all_events_email(email: str) -> list[EventModel]:
        with app.app_context():
            events = EventModel.query.filter_by(email=email).all()
            # Will return nothing if id is invalid
            return events

    @staticmethod
    def all_events_email_days(email: str, days: int) -> list[EventModel]:
        if days == "all":
            days = ALL_DAYS
        timestamp = time.time() - SECONDS_IN_DAY * int(days)
        with app.app_context():
            events = EventModel.query.filter(EventRepository.date > timestamp).filter_by(email=email).all()
            return events


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Export some functions to jinja that we want to use inside html templates
# -------------------------------------------------------------------------------------------------------------- #

# Convert Unix timestamp to human-readable date
def readable_date(timestamp):
    return datetime.utcfromtimestamp(int(timestamp)).strftime('%d/%m/%Y %H:%M:%S')


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(readable_date=readable_date)


# Decide if an event is bad or not (so we can colour it red in the table)
def flag_event(event_type):
    if "fail" in event_type.lower() \
            or event_type == "400" \
            or event_type == "405" \
            or event_type == "500":
        return True
    else:
        for error in range(400, 404):
            if str(error) in event_type.lower():
                return True
    return False


# Decide if an event is good or not (so we can colour it green in the table)
def good_event(event_type):
    if "success" in event_type.lower() or \
            "pass" in event_type.lower():
        return True
    return False


# Flag login and logout (so we can colour them yellow in the table)
def toandfro_event(event_type):
    if "login" in event_type.lower() \
            or "logout" in event_type.lower():
        return True
    return False


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(flag_event=flag_event)
app.jinja_env.globals.update(good_event=good_event)
app.jinja_env.globals.update(toandfro_event=toandfro_event)

