from flask import render_template, request, flash
from flask_wtf.csrf import CSRFError


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_events import Event
from core.main import user_ip


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# ------------------------------------------------------------------------------------------------------------- #
# Generate a 500 error
# ------------------------------------------------------------------------------------------------------------- #

@app.route("/error", methods=['GET'])
def error():
    test = 1 / 0
    return render_template("uncut_steerertubes.html", year=current_year, live_site=live_site())


# ------------------------------------------------------------------------------------------------------------- #
# CSRF Error
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(CSRFError)
def csrf_error(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    flash("Detected a potential Cross Site Request Forgery (CSRF) with the form.")
    flash("NB Forms time out after 60 minutes.")
    app.logger.debug(f"400: CSRF Error '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}', '{request.headers.get('User-Agent')}'.")
    Event().log_event("400", f"CSRF Error for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 400 status explicitly
    return render_template('400.html', year=current_year, live_site=live_site()), 400


# ------------------------------------------------------------------------------------------------------------- #
# 400: Bad Request
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(400)
def bad_request(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"400: Bad request for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}', '{request.headers.get('User-Agent')}'.")
    Event().log_event("400", f"Bad request for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 400 status explicitly
    return render_template('400.html', year=current_year, live_site=live_site()), 400


# ------------------------------------------------------------------------------------------------------------- #
# 401: Unauthorized
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(401)
def unauthorized(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"401: Unauthorized for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}', '{request.headers.get('User-Agent')}'.")
    Event().log_event("401", f"Unauthorized for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 401 status explicitly
    # NB Don't have a 401 page, just re-use 403
    return render_template('403.html', year=current_year, live_site=live_site()), 401


# ------------------------------------------------------------------------------------------------------------- #
# 403: Forbidden
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(403)
def forbidden(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"403: Forbidden for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}', '{request.headers.get('User-Agent')}'.")
    Event().log_event("403", f"Forbidden for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 403 status explicitly
    return render_template('403.html', year=current_year, live_site=live_site()), 403


# ------------------------------------------------------------------------------------------------------------- #
# 404: Not Found
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(404)
def page_not_found(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"404: Not found for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}', '{request.headers.get('User-Agent')}'.")
    Event().log_event("404", f"Not found for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 404 status explicitly
    return render_template('404.html', year=current_year, live_site=live_site()), 404


# ------------------------------------------------------------------------------------------------------------- #
# 405: Method Not Allowed
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(405)
def method_not_allowed(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"405: Not allowed for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}', '{request.headers.get('User-Agent')}'.")
    Event().log_event("405", f"Not allowed for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 405 status explicitly
    return render_template('403.html', year=current_year, live_site=live_site()), 405


# ------------------------------------------------------------------------------------------------------------- #
# 413: Request Entity Too Large
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(413)
def file_too_large(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    flash("The file was too large, limit is 10 MB.")
    app.logger.debug(f"413: File too large for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}', '{request.headers.get('User-Agent')}'.")
    Event().log_event("413", f"File too large for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # note that we set the 413 status explicitly
    return render_template('400.html', year=current_year, live_site=live_site()), 413


# ------------------------------------------------------------------------------------------------------------- #
# 500: Internal server error
# ------------------------------------------------------------------------------------------------------------- #
@app.errorhandler(500)
def internal_server_error(e):
    # What page were they looking for?
    requested_route = request.path
    users_ip = user_ip()

    # Log error in event log
    app.logger.debug(f"500: Internal server error for '{requested_route}', previous page was "
                     f"'{request.referrer}', '{users_ip}', '{request.headers.get('User-Agent')}'.")
    Event().log_event("500", f"Internal server error for '{requested_route}', previous page was "
                             f"'{request.referrer}', '{users_ip}'.")

    # now you're handling non-HTTP exceptions only
    return render_template("500.html", year=current_year, live_site=live_site(), e=e), 500


# Have to register 500 with app to overrule the default built in 500 page
app.register_error_handler(500, internal_server_error)
