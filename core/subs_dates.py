from flask import request, flash
from datetime import datetime
from typing import Optional


def get_date_from_url(return_none_if_empty: bool = False):
    """
    Try and get a date from the url search string and return it in the format DDMMYYYY.
    If there wasn't a date passed, just return today's date.
    Handle the following formats:
        1. date=08/10/2024
        2. date=08102024

    :param return_none:         Determines behaviour if no date is found
    :return:                    str: date in format DDMMYYYY
    """
    # See what we get
    try:
        date_str = request.args.get('date', None).replace("/", "")
    except Exception:
        date_str = None

    # Validate
    try:
        datetime.strptime(date_str, '%d%m%Y')
        return date_str
    except Exception:
        flash(f"Didn't understand the date '{date_str}'")
        if return_none_if_empty:
            return None
        else:
            # If we weren't given a date, just use today
            today = datetime.today()
            return today.strftime("%d%m%Y")
