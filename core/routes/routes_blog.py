from flask import render_template, request, flash, abort, redirect, url_for, send_from_directory, Response
from flask_login import current_user
from werkzeug import exceptions
import os
from datetime import date, datetime, timedelta
from threading import Thread
from ics import Calendar as icsCalendar, Event as icsEvent


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year, live_site, BLOG_IMAGE_FOLDER, ICS_DIRECTORY


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.user_repository import UserRepository, SUPER_ADMIN_USER_ID
from core.database.repositories.blog_repository import (BlogRepository as Blog, Privacy, Sticky,
                                                        NO_CAFE, NO_GPX, Category)
from core.forms.blog_forms import create_blogs_form
from core.database.repositories.event_repository import EventRepository
from core.database.repositories.cafe_repository import CafeRepository
from core.database.repositories.gpx_repository import GpxRepository
from core.subs_blog_photos import update_blog_photo, delete_blog_photos
from core.subs_email_sms import alert_admin_via_sms, send_blog_notification_emails
from core.database.repositories.message_repository import MessageRepository, ADMIN_EMAIL

from core.decorators.user_decorators import update_last_seen, logout_barred_user, login_required, rw_required


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

PAGE_SIZE = 10
FIRST_PAGE = 0


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Show blog list or one particular blog
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/blog", methods=['GET'])
@update_last_seen
def display_blog() -> Response:
    # ----------------------------------------------------------- #
    # Did we get passed a blog_id? (Optional)
    # ----------------------------------------------------------- #
    blog_id = request.args.get('blog_id', None)
    page = request.args.get('page', None)

    # ----------------------------------------------------------- #
    # Validate page
    # ----------------------------------------------------------- #
    if page:
        # Must be integer (get string back from html)
        try:
            page = int(page)
        except:
            # Handle being passed garbage
            page = None

    # ----------------------------------------------------------- #
    # Validate blog_id
    # ----------------------------------------------------------- #
    if blog_id:
        blog = Blog().one_by_id(blog_id)
        if not blog:
            app.logger.debug(f"blog(): Failed to locate blog, blog_id = '{blog_id}'.")
            EventRepository().log_event("Blog Fail", f"Failed to locate blog, blog_id = '{blog_id}''.")
            flash("Sorry, looks like that Blog post has been deleted...")
            return abort(404)
    else:
        blog = None

    # ----------------------------------------------------------- #
    # Permissions (only apply if trying to see a Private blog post)
    # ----------------------------------------------------------- #
    if blog:
        if blog.private == Privacy.PRIVATE:
            # Need to check user is trusted
            if not current_user.is_authenticated:
                # Not logged in
                app.logger.debug(f"blog(): Refusing permission for unregistered user.")
                EventRepository().log_event("Blog Fail", f"Refusing permission for unregistered user.")
                flash("You must be logged in to see private blog posts!")
                return redirect(url_for("not_logged_in"))

            elif not current_user.readwrite:
                # Failed authentication
                app.logger.debug(f"blog(): Refusing permission for '{current_user.email}'.")
                EventRepository().log_event("Blog Fail", f"Refusing permission for '{current_user.email}'.")
                flash("You do not have permission to see private blog posts!")
                return redirect(url_for("not_rw"))

    # ----------------------------------------------------------- #
    # List of all news articles
    # ----------------------------------------------------------- #
    # Did they request a specific blog post?
    if blog:
        # Just this one
        blogs = [blog]
        # Tell jinja to ignore pagination
        page = None
    elif page:
        # They have requested a specific page
        blogs = Blog().all_non_sticky(page, PAGE_SIZE)
        print(f"Used page = '{page}' and got back '{len(blogs)}' blogs...")
    else:
        # No page specified so just do front page
        blogs = Blog().all_sticky()
        print(f"Found {len(blogs)} sticky blogs...")
        # Then we add a number of non sticky ones
        # NB This means the first page will be slightly longer than normal as we add stickies
        # but, otherwise pagination would be a PITA as we'd have to offset every page by the number
        # of stickies in the first page and I really can't be arsed...
        # Tell jinja which page this is
        page = FIRST_PAGE
        blogs = blogs + Blog().all_non_sticky(page, PAGE_SIZE)

    # jinja will need to know how many pages there are...
    num_pages = Blog().number_pages(PAGE_SIZE)

    # ----------------------------------------------------------- #
    # Add some extra things for jinja
    # ----------------------------------------------------------- #
    for blog in blogs:

        # 1. Human-readable date
        if blog.date_unix:
            blog.date = datetime.utcfromtimestamp(blog.date_unix).strftime('%d %b %Y')

        # Get image filename and pass to Jinja (if present)
        blog.filename = None
        if blog.image_filename:
            filename = f"/img/blog_photos/{blog.image_filename}"
            # Check file(s) actually exist
            if os.path.exists(os.path.join(BLOG_IMAGE_FOLDER, os.path.basename(filename))):
                blog.filename = filename

    return render_template("blog.html", year=current_year, blogs=blogs, no_cafe=0, no_gpx=0, page=page,
                           num_pages=num_pages, page_size=PAGE_SIZE, event_option=Category.EVENT, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Download ics file for Blog Event
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/blog_ics", methods=['GET', 'POST'])
@update_last_seen
@logout_barred_user
@login_required
def blog_ics() -> Response:
    # ----------------------------------------------------------- #
    # Did we get passed a blog_id?
    # ----------------------------------------------------------- #
    blog_id = request.args.get('blog_id', None)

    # ----------------------------------------------------------- #
    # Must have parameters
    # ----------------------------------------------------------- #
    if not blog_id:
        app.logger.debug(f"blog_ics(): Missing blog_id.")
        EventRepository().log_event("Blog ICS Fail", f"Missing blog_id.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Validate blog_id
    # ----------------------------------------------------------- #
    blog = Blog().one_by_id(blog_id)
    if not blog:
        app.logger.debug(f"blog_icsg(): Failed to locate blog, blog_id = '{blog_id}'.")
        EventRepository().log_event("Blog ICS Fail", f"Failed to locate blog, blog_id = '{blog_id}''.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Create ics file
    # ----------------------------------------------------------- #
    new_event = icsEvent()
    new_event.name = f"ELSR Event: {blog.title}"
    # NB Time is set to midnight as we don't have start times in the Blog db (currently)
    new_event.begin = f"{datetime.utcfromtimestamp(blog.date_unix).strftime('%Y-%m-%d')} 00:00:00"
    new_event.description = blog.details

    # Add to ics calendar
    new_cal = icsCalendar()
    new_cal.events.add(new_event)

    # Save as file
    filename = os.path.join(ICS_DIRECTORY, f"Blog_Event_{blog.id}.ics")
    with open(filename, 'w') as my_file:
        my_file.writelines(new_cal.serialize_iter())

    # ----------------------------------------------------------- #
    # Send link to download the file
    # ----------------------------------------------------------- #
    download_name = f"ELSR_Event_{blog.id}.ics"

    app.logger.debug(f"download_ics(): Serving ICS blog_id = '{blog_id}' ({blog.title}), "
                     f"download_name = '{download_name}'.")
    EventRepository().log_event("ICS Downloaded", f"Serving ICS blog_id = '{blog_id}' ({blog.title}).")
    return send_from_directory(directory=ICS_DIRECTORY,
                               path=os.path.basename(filename),
                               download_name=download_name)

