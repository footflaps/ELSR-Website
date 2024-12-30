from datetime import datetime


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import app


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
app.jinja_env.globals.update(readable_date=readable_date)
app.jinja_env.globals.update(flag_event=flag_event)
app.jinja_env.globals.update(good_event=good_event)
app.jinja_env.globals.update(toandfro_event=toandfro_event)
