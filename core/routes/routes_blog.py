from flask import render_template, request, flash, abort, redirect, url_for, send_from_directory
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
def display_blog():
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
        blog = Blog().find_blog_from_id(blog_id)
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
        blogs = Blog().non_sticky(page, PAGE_SIZE)
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
        blogs = blogs + Blog().non_sticky(page, PAGE_SIZE)

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
# Add / edit a blog post
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/add_blog", methods=['GET', 'POST'])
@app.route("/edit_blog", methods=['GET', 'POST'])
@update_last_seen
@logout_barred_user
@login_required
@rw_required
def add_blog():
    # ----------------------------------------------------------- #
    # Did we get passed a blog_id? (Optional)
    # ----------------------------------------------------------- #
    blog_id = request.args.get('blog_id', None)

    # ----------------------------------------------------------- #
    # Validate blog_id
    # ----------------------------------------------------------- #
    if blog_id:
        blog = Blog().find_blog_from_id(blog_id)
        if not blog:
            app.logger.debug(f"add_blog(): Failed to locate blog, blog_id = '{blog_id}'.")
            EventRepository().log_event("Edit Blog Fail", f"Failed to locate blog, blog_id = '{blog_id}''.")
            return abort(404)
    else:
        blog = None

    print("blog", blog)

    # ----------------------------------------------------------- #
    # Work out what we're doing (Add / Edit)
    # ----------------------------------------------------------- #
    if blog_id and request.method == 'GET':

        # ----------------------------------------------------------- #
        # Edit event, so pre-fill form from dB
        # ----------------------------------------------------------- #
        # Get a blank form
        form = create_blogs_form(current_user.admin)

        # Now fill the form in....
        form.date.data = datetime.fromtimestamp(blog.date_unix)
        form.title.data = blog.title
        form.category.data = blog.category
        if blog.cafe_id == NO_CAFE:
            form.cafe.data = NO_CAFE
        else:
            form.cafe.data = CafeRepository().one_cafe(blog.cafe_id).combo_string()
        if blog.gpx_index == NO_GPX:
            form.gpx.data = NO_GPX
        else:
            form.gpx.data = GpxRepository().one_by_id(blog.gpx_index).combo_string()
        form.details.data = blog.details

        if blog.private:
            form.privacy.data = Privacy.PRIVATE.value
        else:
            form.privacy.data = Privacy.PUBLIC.value

        # Admin things
        if current_user.admin:
            form.owner.data = UserRepository().find_user_from_email(blog.email).combo_str
            if blog.sticky:
                form.sticky.data = Sticky.TRUE.value
            else:
                form.sticky.data = Sticky.FALSE.value
    else:
        # ----------------------------------------------------------- #
        # Add event, so start with fresh form
        # ----------------------------------------------------------- #
        form = create_blogs_form(current_user.admin)

        # Fill in today's date
        if request.method == 'GET':
            form.date.data = date.today()
            if current_user.admin:
                form.owner.data = UserRepository().find_user_from_id(current_user.id).combo_str

    # Are we posting the completed comment form?
    if request.method == 'POST' \
            and form.validate_on_submit():
        # ----------------------------------------------------------- #
        # Handle form passing validation
        # ----------------------------------------------------------- #

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('display_blog'))

        # ----------------------------------------------------------- #
        # Validate contents
        # ----------------------------------------------------------- #
        # Killjoy!
        if form.category.data == Category.DRUNK_OPTION:
            flash("Best not post stuff when drunk!")
            return render_template("blog_new.html", year=current_year, form=form, live_site=live_site())
        elif form.category.data == Category.CCC_OPTION:
            flash("Yep, we all know they're miserable bastards, but no need to shout about it!")
            return render_template("blog_new.html", year=current_year, form=form, live_site=live_site())

        # ----------------------------------------------------------- #
        # Create new_blog instance
        # ----------------------------------------------------------- #
        if blog:
            # Updating an existing blog entry
            new_blog = blog
        else:
            # New post
            new_blog = Blog()

        # ----------------------------------------------------------- #
        # Populate new_blog from form
        # ----------------------------------------------------------- #

        # 1. Date
        if type(form.date.data) == datetime:
            formdate = form.date.data.date()
        else:
            formdate = form.date.data

        # Convert to Unix time
        # We add two hours to get round the day changing due to BST / GMT and converting back and forth
        new_blog.date_unix = datetime.timestamp(datetime.combine(formdate, datetime.min.time()) + timedelta(hours=2))

        # 2. The rest
        new_blog.title = form.title.data
        new_blog.category = form.category.data
        new_blog.cafe_id = CafeRepository().cafe_id_from_combo_string(form.cafe.data)
        new_blog.gpx_index = GpxRepository().gpx_id_from_combo_string(form.gpx.data)
        new_blog.details = form.details.data
        new_blog.private = form.privacy.data == Privacy.PRIVATE.value

        # 3. Admin fields
        if current_user.admin:
            new_blog.email = UserRepository().user_from_combo_string(form.owner.data).email
            new_blog.sticky = form.sticky.data == Sticky.TRUE.value
        else:
            new_blog.sticky = False
            new_blog.email = current_user.email

        # 4. Image filename
        if blog:
            # Move across existing image filename
            new_blog.image_filename = blog.image_filename

        # ----------------------------------------------------------- #
        # Try and add the blog post
        # ----------------------------------------------------------- #
        # Need to add before we upload the photo as we need new_blog to have a valid id
        new_blog = Blog().add_blog(new_blog)
        if not new_blog:
            # Should never happen, but...
            app.logger.debug(f"add_blog(): Failed to add ride from '{new_blog}'.")
            EventRepository().log_event("Add blog Fail", f"Failed to add ride '{new_blog}'.")
            flash("Sorry, something went wrong.")
            return render_template("blog_new.html", year=current_year, form=form, live_site=live_site())

        # ----------------------------------------------------------- #
        #   Did we get passed a path for a photo?
        # ----------------------------------------------------------- #
        if form.photo_filename.data.filename != "":
            # Upload the photo
            update_blog_photo(form, new_blog)

        # ----------------------------------------------------------- #
        #   Success
        # ----------------------------------------------------------- #
        app.logger.debug(f"add_blog(): Successfully added new blog post.")
        EventRepository().log_event("Add Blog Pass", f"Successfully added new blog post.")
        if blog:
            flash("Blog updated!")
        else:
            flash("New Blog created!")
            user = UserRepository().find_user_from_id(current_user.id)
            Thread(target=send_blog_notification_emails, args=(new_blog,)).start()
            # Suppress SMS alerts for me as I post 95% of blogs and I'm just wasting my own money alerting myself!
            if current_user.id != SUPER_ADMIN_USER_ID:
                Thread(target=alert_admin_via_sms, args=(user, "New blog post alert, please check it's OK!",)).start()

        # Point them at their blog entry
        return redirect(url_for('display_blog', blog_id=new_blog.id))

    # ----------------------------------------------------------- #
    # Handle POST (but form validation failed)
    # ----------------------------------------------------------- #
    elif request.method == 'POST':

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('display_blog'))

        # This traps a post, but where the form verification failed.
        flash("Something was missing, see comments below:")
        return render_template("blog_new.html", year=current_year, form=form, live_site=live_site())

    # ----------------------------------------------------------- #
    # Handle GET
    # ----------------------------------------------------------- #

    return render_template("blog_new.html", year=current_year, form=form, live_site=live_site())


# -------------------------------------------------------------------------------------------------------------- #
# Delete a blog post
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/delete_blog", methods=['POST'])
@update_last_seen
@logout_barred_user
@login_required
def delete_blog():
    # ----------------------------------------------------------- #
    # Did we get passed a blog_id?
    # ----------------------------------------------------------- #
    blog_id = request.args.get('blog_id', None)
    try:
        password = request.form['password']
    except exceptions.BadRequestKeyError:
        password = None
    try:
        reason = request.form['reason']
    except exceptions.BadRequestKeyError:
        reason = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if password == "":
        password = " "
    if reason == "":
        reason = " "

    # ----------------------------------------------------------- #
    # Get user's IP
    # ----------------------------------------------------------- #
    if request.headers.getlist("X-Forwarded-For"):
        user_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        user_ip = request.remote_addr

    # ----------------------------------------------------------- #
    # Must have parameters
    # ----------------------------------------------------------- #
    if not blog_id:
        app.logger.debug(f"delete_blog(): Missing blog_id!")
        EventRepository().log_event("Delete Blog Fail", f"Missing blog_id!")
        return abort(400)
    if not password:
        app.logger.debug(f"delete_blog(): Missing Password!")
        EventRepository().log_event("Delete Blog Fail", f"Missing Password!")
        return abort(400)
    if not reason:
        app.logger.debug(f"delete_blog(): Missing Reason!")
        EventRepository().log_event("Delete Blog Fail", f"Missing Reason!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate blog_id
    # ----------------------------------------------------------- #
    blog = Blog().find_blog_from_id(blog_id)
    if not blog:
        app.logger.debug(f"delete_blog(): Failed to locate blog, blog_id = '{blog_id}'.")
        EventRepository().log_event("Delete Blog Fail", f"Failed to locate blog, blog_id = '{blog_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access to Admin and Author
    # ----------------------------------------------------------- #
    # Must be admin or the current author
    if current_user.email != blog.email \
            and not current_user.admin or \
            not current_user.readwrite:
        # Failed authentication
        app.logger.debug(f"delete_blog(): Refusing permission for '{current_user.email}' and "
                         f"blog_id = '{blog_id}'.")
        EventRepository().log_event("Delete Blog Fail", f"Refusing permission for '{current_user.email}', "
                                              f"blog_id = '{blog_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Must give a reason
    # ----------------------------------------------------------- #
    if reason.strip() == "":
        app.logger.debug(f"delete_blog(): Reason was blank, blog_id = '{blog_id}'.")
        EventRepository().log_event("Delete Blog Fail", f"Reason was blank, blog_id = '{blog_id}'.")
        flash("You must give a reason to delete a blog post!")
        return redirect(url_for('display_blog', blog_id=blog_id))

    # ----------------------------------------------------------- #
    #  Validate password
    # ----------------------------------------------------------- #
    # Need current user
    user = UserRepository().find_user_from_id(current_user.id)

    # Validate against current_user's password
    if not user.validate_password(user, password, user_ip):
        app.logger.debug(f"delete_blog(): Delete failed, incorrect password for user_id = '{user.id}'!")
        EventRepository().log_event("Delete Blog Fail", f"Incorrect password for user_id = '{user.id}'!")
        flash(f"Incorrect password for user {user.name}!")
        # Go back to blogs page
        return redirect(url_for('display_blog'))

    # ----------------------------------------------------------- #
    # Delete blog photos first
    # ----------------------------------------------------------- #
    delete_blog_photos(blog)

    # ----------------------------------------------------------- #
    # Message owner
    # ----------------------------------------------------------- #
    if user.email != blog.email:
        # Create a new message
        new_message = MessageRepository(
            from_email=ADMIN_EMAIL,
            to_email=blog.email,
            body=f"Sorry, an Admin has deleted your blog '{blog.title}'. The reason given was '{reason}'."
        )
        # Send the message
        if MessageRepository().add_message(new_message):
            # Success!
            app.logger.debug(f"delete_blog(): Sent blog delete message to '{blog.email}'.")
            EventRepository().log_event("Delete Blog Pass", f"Sent blog delete message to '{blog.email}'.")
        else:
            # Should never get here, but...
            app.logger.debug(f"delete_blog(): Message().add_message() failed, blog.email = '{blog.email}'.")
            EventRepository().log_event("Delete Blog Fail", f"Message().add_message() failed, blog.email = '{blog.email}'.")

    # ----------------------------------------------------------- #
    # Delete blog
    # ----------------------------------------------------------- #
    if Blog().delete_blog(blog_id):
        app.logger.debug(f"delete_blog(): Deleted blog, reason = '{reason}', blog_id = '{blog_id}'.")
        EventRepository().log_event("Delete Blog Success", f"Deleted blog, reason = '{reason}', blog_id = '{blog_id}'.")
        flash("Blog has been deleted.")
    else:
        app.logger.debug(f"delete_blog(): Failed to delete Blog, blog_id = '{blog_id}'.")
        EventRepository().log_event("Delete Blog Fail", f"Failed to delete Blog, blog_id = '{blog_id}'.")
        flash("Sorry, something went wrong.")

    return redirect(url_for('display_blog'))


# -------------------------------------------------------------------------------------------------------------- #
# Download ics file for Blog Event
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/blog_ics", methods=['GET', 'POST'])
@update_last_seen
@logout_barred_user
@login_required
def blog_ics():
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
    blog = Blog().find_blog_from_id(blog_id)
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

