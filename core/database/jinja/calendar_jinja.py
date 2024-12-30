from core import app
from core.database.repositories.calendar_repository import DEFAULT_START_TIMES, MEETING_OTHER


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
