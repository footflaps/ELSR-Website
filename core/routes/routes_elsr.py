from flask import render_template, request, flash, send_from_directory, url_for, redirect, Response
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, SubmitField
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from threading import Thread


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site, GLOBAL_FLASH


# -------------------------------------------------------------------------------------------------------------- #
# Import our Decorators
# -------------------------------------------------------------------------------------------------------------- #

from core.decorators.user_decorators import update_last_seen


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.cafe_repository import CafeModel, CafeRepository, OPEN_CAFE_COLOUR, BEAN_THEORY_INDEX
from core.database.repositories.user_repository import UserModel, UserRepository
from core.subs_google_maps import google_maps_api_key, ELSR_HOME, MAP_BOUNDS, count_map_loads
from core.subs_email import contact_form_email


# -------------------------------------------------------------------------------------------------------------- #
# Contact form
# -------------------------------------------------------------------------------------------------------------- #

class ContactForm(FlaskForm):
    name = StringField("Name", validators=[InputRequired("Please enter your name.")])
    email = EmailField("Email address", validators=[InputRequired("Please enter your email address.")])
    message = CKEditorField("Message", validators=[InputRequired("Please enter a message.")])
    submit = SubmitField("Send")


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# robots.txt
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/robots.txt')
def static_from_root() -> Response | str:
    # ----------------------------------------------------------- #
    # Send link to download the file
    # ----------------------------------------------------------- #
    filename = request.path[1:]

    return send_from_directory(directory="../core/static/", path=filename)


# -------------------------------------------------------------------------------------------------------------- #
# Front page
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/', methods=['GET'])
@update_last_seen
def welcome() -> Response | str:
    # -------------------------------------------------------------------------------------------- #
    # Decide where to send them
    # -------------------------------------------------------------------------------------------- #

    if current_user.is_authenticated:
        # Logged in users see the blog
        return redirect(url_for('display_blog'))  # type: ignore
    else:
        # New users see home
        return redirect(url_for('home'))  # type: ignore


# -------------------------------------------------------------------------------------------------------------- #
# Home
# -------------------------------------------------------------------------------------------------------------- #
@app.route('/home', methods=['GET'])
@update_last_seen
def home() -> Response | str:
    # -------------------------------------------------------------------------------------------- #
    # Show Current Meeting Place
    # -------------------------------------------------------------------------------------------- #

    # Get the cafe
    cafe: CafeModel | None = CafeRepository.one_by_id(BEAN_THEORY_INDEX)

    if cafe:
        # Create a GM marker
        cafe_marker = [{
            "position": {"lat": cafe.lat, "lng": cafe.lon},
            "title": f'<a href="{url_for("cafe_details", cafe_id=BEAN_THEORY_INDEX)}">{cafe.name}</a>',
            "color": OPEN_CAFE_COLOUR,
        }]
    else:
        cafe_marker = []

    # Increment map counts
    count_map_loads(1)

    # Temporary alert for change of meeting point
    if GLOBAL_FLASH:
        flash(GLOBAL_FLASH)

    # Render home page
    return render_template("main_home.html", year=current_year, cafes=cafe_marker, live_site=live_site(),
                           GOOGLE_MAPS_API_KEY=google_maps_api_key(), ELSR_HOME=ELSR_HOME, MAP_BOUNDS=MAP_BOUNDS)


# -------------------------------------------------------------------------------------------------------------- #
# About
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/about", methods=['GET'])
@update_last_seen
def about() -> Response | str:
    return render_template("main_about.html", year=current_year, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# GDPR
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/gdpr", methods=['GET'])
@update_last_seen
def gdpr() -> Response | str:
    # ----------------------------------------------------------- #
    # List of all admins
    # ----------------------------------------------------------- #
    admins = UserRepository.all_admins()

    return render_template("main_gdpr.html", year=current_year, admins=admins, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Contact
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/contact", methods=['GET', 'POST'])
@update_last_seen
def contact() -> Response | str:
    # Need a form
    form = ContactForm()

    # Are we posting the completed form?
    if form.validate_on_submit():

        # ----------------------------------------------------------- #
        #   POST - form validated & submitted
        # ----------------------------------------------------------- #

        # Detect SPAM
        if any(word in str(form.message).lower() for word in ["http", "www", "tinyurl", "/", "unsubscribe", "sales", "marketing", "offer", "promotional"]):
            flash("Sorry, No spam.")
            return render_template("main_contact.html", year=current_year, form=form, live_site=live_site())

        Thread(target=contact_form_email, args=(form.name.data, form.email.data, form.message.data,)).start()
        flash("Thankyou, your message has been sent!")

        # Clear the form
        form.email.data = ""
        form.name.data = ""
        form.message.data = ""

    elif request.method == 'POST':

        # ----------------------------------------------------------- #
        #   POST - form validation failed
        # ----------------------------------------------------------- #

        flash("Form not filled in properly, see below!")

    # ----------------------------------------------------------- #
    #   GET - Render page
    # ----------------------------------------------------------- #

    return render_template("main_contact.html", year=current_year, form=form, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# How to plan a ride
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/plan", methods=['GET'])
@update_last_seen
def plan() -> Response | str:
    return render_template("main_plan_a_ride.html", year=current_year, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# How to download a GPX
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/gpx_guide", methods=['GET'])
@update_last_seen
def gpx_guide() -> Response | str:
    return render_template("main_download_howto.html", year=current_year, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Uncut steerer tubes
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/uncut", methods=['GET'])
@update_last_seen
def uncut() -> Response | str:
    return render_template("uncut_steerertubes.html", year=current_year, live_site=live_site())
