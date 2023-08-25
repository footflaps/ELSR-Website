from flask import render_template, url_for, request, flash, redirect, abort
from flask_login import login_required, current_user
from werkzeug import exceptions
from bbc_feeds import weather
from datetime import datetime
import calendar as cal
import json
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import update_last_seen, logout_barred_user
from core.db_calendar import Calendar


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Weekend ride details
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/calendar', methods=['GET'])
@logout_barred_user
@update_last_seen
def calendar():
    # ----------------------------------------------------------- #
    # Need to build a list of events
    # ----------------------------------------------------------- #
    events = []

    # Loop over time
    year = datetime.today().year
    month = datetime.today().month
    # Just cover next 6 months
    for _ in range(0, 7):
        if month == 13:
            year += 1
            month = 1
        for day in range(1, cal.monthrange(year, month)[1] + 1):
            day_of_week = datetime(year, month, day, 0, 00).strftime("%A")
            datestr = f"{format(day, '02d')}{format(month, '02d')}{year}"
            if Calendar().all_calendar_date(datestr):
                events.append({
                    "date": f"{year}-{format(month, '02d')}-{format(day, '02d')}",
                    "markup": f"<a href='{url_for('weekend', date=f'{datestr}')}'>"
                              f"<i class='fas fa-solid fa-person-biking fa-2xl'></i>[day]</a>",
                })
            # Need Pro icons for this to work
            # elif day_of_week == "Saturday" \
            #         or day_of_week == "Sunday":
            #     events.append({
            #         "date": f"{year}-{format(month, '02d')}-{format(day, '02d')}",
            #         "markup": f"<i class='fas fa-thin fa-person-biking fa-xl'></i>[day]",
            #     })
        # Next month
        month += 1

    # Add a chaingang or two
    events.append({
        "date": "2023-08-03",
        "markup": f"<a href='{url_for('chaingang')}'><i class='fas fa-solid fa-arrows-spin fa-spin fa-xl'></i>[day]</a>"
    })
    events.append({
        "date": "2023-08-10",
        "markup": f"<a href='{url_for('chaingang')}'><i class='fas fa-solid fa-arrows-spin fa-spin fa-xl'></i>[day]</a>"
    })
    events.append({
        "date": "2023-08-17",
        "markup": f"<a href='{url_for('chaingang')}'><i class='fas fa-solid fa-arrows-spin fa-spin fa-xl'></i>[day]</a>"
    })
    events.append({
        "date": "2023-08-24",
        "markup": f"<a href='{url_for('chaingang')}'><i class='fas fa-solid fa-arrows-spin fa-spin fa-xl'></i>[day]</a>"
    })
    events.append({
        "date": "2023-08-31",
        "markup": f"<a href='{url_for('chaingang')}'><i class='fas fa-solid fa-arrows-spin fa-spin fa-xl'></i>[day]</a>"
    })
    events.append({
        "date": "2023-09-07",
        "markup": f"<a href='{url_for('chaingang')}'><i class='fas fa-solid fa-arrows-spin fa-spin fa-xl'></i>[day]</a>"
    })
    events.append({
        "date": "2023-09-14",
        "markup": f"<a href='{url_for('chaingang')}'><i class='fas fa-solid fa-arrows-spin fa-spin fa-xl'></i>[day]</a>"
    })
    events.append({
        "date": "2023-09-21",
        "markup": f"<a href='{url_for('chaingang')}'><i class='fas fa-solid fa-arrows-spin fa-spin fa-xl'></i>[day]</a>"
    })
    events.append({
        "date": "2023-09-28",
        "markup": f"<a href='{url_for('chaingang')}'><i class='fas fa-solid fa-arrows-spin fa-spin fa-xl'></i>[day]</a>"
    })

    # Add a social
    events.append({
        "date": "2023-09-23",
        "markup": f"<a href='{url_for('social')}'><i class='fas fa-solid fa-champagne-glasses fa-bounce fa-2xl'></i>[day]</a>"
    })

    return render_template("calendar.html", year=current_year, events=events)

