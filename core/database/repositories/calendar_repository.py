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
                db.rollback()
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
                    db.rollback()
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
                    db.rollback()
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
    def one_ride_id(ride_id):
        with app.app_context():
            ride = CalendarModel.query.filter_by(id=ride_id).first()
            # Will return nothing if id is invalid
            return ride

    @staticmethod
    def all_rides_gpx_id(gpx_id):
        with app.app_context():
            rides = CalendarModel.query.filter_by(gpx_id=gpx_id).all()
            # Will return nothing if id is invalid
            return rides


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Convert the dictionary entry into a single string
# -------------------------------------------------------------------------------------------------------------- #
def start_time_string(start_time_dict):
    if start_time_dict['location'] != MEETING_OTHER:
        return f"{start_time_dict['time']} from {start_time_dict['location']}"
    else:
        return f"{start_time_dict['time']} from {start_time_dict['new']}"


# -------------------------------------------------------------------------------------------------------------- #
# Return the default start time for a given day as html
# -------------------------------------------------------------------------------------------------------------- #
def default_start_time_html(day):
    # Look up what we would normally expect for day 'day'
    default_time = DEFAULT_START_TIMES[day]['time']
    if DEFAULT_START_TIMES[day]['location'] != MEETING_OTHER:
        default_location = DEFAULT_START_TIMES[day]['location']
    else:
        default_location = DEFAULT_START_TIMES[day]['new']

    return f"<strong>{default_time}</strong> from <strong>{default_location}</strong>"


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(default_start_time_html=default_start_time_html)


# -------------------------------------------------------------------------------------------------------------- #
# Return a custom start time as an html string
# -------------------------------------------------------------------------------------------------------------- #

def custom_start_time_html(day, start_time_str):
    # Look up what we would normally expect for day 'day'
    default_time = DEFAULT_START_TIMES[day]['time']
    if DEFAULT_START_TIMES[day]['location'] != MEETING_OTHER:
        default_location = DEFAULT_START_TIMES[day]['location']
    else:
        default_location = DEFAULT_START_TIMES[day]['new']

    # Now parse actual string
    # We expect the form "Doppio", "Danish Camp", "08:00 from Bean Theory Cafe" etc
    # Split "08:00" from "from Bean Theory Cafe"
    time = start_time_str.split(' ')[0]
    location = " ".join(start_time_str.split(' ')[2:])

    # Build our html string
    if default_time == time:
        html = f"<strong>{time}</strong>"
    else:
        html = f"<strong style='color: red'>{time}</strong>"

    if default_location == location:
        html += f" from <strong>{location}</strong>"
    else:
        html += f" from <strong style='color:red'>{location}</strong>"

    return html


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(custom_start_time_html=custom_start_time_html)


# -------------------------------------------------------------------------------------------------------------- #
# Convert date from '11112023' to '11/11/2023' as more user friendly
# -------------------------------------------------------------------------------------------------------------- #

def beautify_date(date: str):
    # Check we have been passed a string in the right format
    if len(date) != 8:
        # Just pass it back to be displayed as is
        return date
    return f"{date[0:2]}/{date[2:4]}/{date[4:9]}"


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(beautify_date=beautify_date)
