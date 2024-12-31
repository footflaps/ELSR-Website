from datetime import datetime, timedelta
import time


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db, GROUP_CHOICES
from core.database.models.calendar_model import CalendarModel


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Option for user defined choices
NEW_CAFE = "New cafe!"
UPLOAD_ROUTE = "Upload my own route!"

# Options for where the rides start
MEETING_OTHER = "Other..."
MEETING_BEAN = "Bean Theory Cafe"
MEETING_COFFEE_VANS = "Coffee Vans by the Station"
MEETING_TWR = "The Bench, Newnham Corner"
MEETING_CHOICES = [MEETING_BEAN,
                   MEETING_COFFEE_VANS,
                   MEETING_OTHER]

# Used by JS on the create ride page to autofill in the start details based on the day of week
DEFAULT_START_TIMES = {"Monday": {'time': '08:00', 'location': MEETING_BEAN, 'new': ''},
                       "Tuesday": {'time': '08:00', 'location': MEETING_BEAN, 'new': ''},
                       "Wednesday": {'time': '08:00', 'location': MEETING_OTHER, 'new': MEETING_TWR},
                       "Thursday": {'time': '08:00', 'location': MEETING_BEAN, 'new': ''},
                       "Friday": {'time': '08:00', 'location': MEETING_BEAN, 'new': ''},
                       "Saturday": {'time': '08:00', 'location': MEETING_BEAN, 'new': ''},
                       "Sunday": {'time': '09:00', 'location': MEETING_BEAN, 'new': ''},
                       }


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Calendar Repository Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class CalendarRepository(CalendarModel):

    # -------------------------------------------------------------------------------------------------------------- #
    # Create
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def add_ride(new_ride):
        # Add unix time
        date_obj = datetime(int(new_ride.date[4:8]), int(new_ride.date[2:4]), int(new_ride.date[0:2]), 0, 00)
        date_unix = datetime.timestamp(datetime.combine(date_obj, datetime.min.time()) + timedelta(hours=2))
        new_ride.unix_date = date_unix

        # Try and add to dB
        with app.app_context():
            try:
                db.session.add(new_ride)
                db.session.commit()
                # Have to re-acquire the message to return it (else we get Detached Instance Error)
                return CalendarModel.query.filter_by(id=new_ride.id).first()

            except Exception as e:
                db.session.rollback()
                app.logger.error(f"db_calendar: Failed to add ride '{new_ride}', "
                                 f"error code '{e.args}'.")
                return None

    # -------------------------------------------------------------------------------------------------------------- #
    # Modify
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def mark_email_sent(ride_id):
        with app.app_context():
            ride = CalendarModel.query.filter_by(id=ride_id).first()
            if ride:
                # Modify
                try:
                    ride.sent_email = "True"
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_calendar: Failed to set email sent for ride_id = '{ride.id}', "
                                     f"error code '{e.args}'.")

        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Delete
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def delete_ride(ride_id):
        with app.app_context():
            ride = CalendarModel.query.filter_by(id=ride_id).first()
            if ride:
                # Delete the ride file
                try:
                    db.session.delete(ride)
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_calendar: Failed to delete ride for ride_id = '{ride.id}', "
                                     f"error code '{e.args}'.")

        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Search
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def all_calendar():
        with app.app_context():
            rides = CalendarModel.query.all()
            return rides

    # Return all events from a given user
    @staticmethod
    def all_calendar_email(email):
        with app.app_context():
            rides = CalendarModel.query.filter_by(email=email).all()
            # Will return nothing if email is invalid
            return rides

    # Return all events for a specific day
    @staticmethod
    def all_calendar_date(ride_date: str):
        with app.app_context():
            rides = []
            # We want them ordered by group so they are ordered on the webpage
            for group in GROUP_CHOICES:
                ride_set = CalendarModel.query.filter_by(date=ride_date).filter_by(group=group).all()
                for ride in ride_set:
                    rides.append(ride)
            return rides

    @staticmethod
    def all_by_date_range(start_date: str, end_date: str) -> list[CalendarModel] | None:
        """
        Retrieve all rides that fall between two dates based on the converted_date column.
        :param start_date:                  Start date in the format 'YYYY-MM-DD'.
        :param end_date:                    End date in the format 'YYYY-MM-DD'.
        :return:                            List of rides between the specified dates.
        """
        with app.app_context():
            try:
                rides = CalendarModel.query.filter(CalendarModel.converted_date.between(start_date, end_date)).all()
                return rides

            except Exception as e:
                app.logger.error(f"db_calendar: Failed to filter rides by date range, "
                                 f"error code '{e.args}'.")
                return None

    @staticmethod
    def all_calender_group_in_past(group: str):
        # Get current Unix Epoch time, plus a bit (6 hours)
        # This is because we add 2 hours to Unix Epoch timestamps to get round GMT/BST problem
        now = time.time() + 60 * 60 * 6
        with app.app_context():
            rides = CalendarModel.query.filter_by(group=group). \
                filter(CalendarRepository.unix_date < now).order_by(CalendarRepository.unix_date.desc()).all()
            return rides

    # Look up event by ID
    @staticmethod
    def one_by_id(id):
        with app.app_context():
            ride = CalendarModel.query.filter_by(id=id).first()
            # Will return nothing if id is invalid
            return ride

    @staticmethod
    def all_rides_gpx_id(gpx_id):
        with app.app_context():
            rides = CalendarModel.query.filter_by(gpx_id=gpx_id).all()
            # Will return nothing if id is invalid
            return rides
