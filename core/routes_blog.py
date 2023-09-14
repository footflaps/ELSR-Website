from flask import render_template, request, flash, abort, send_from_directory, redirect, url_for
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFError
from wtforms import StringField, EmailField, SubmitField
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from threading import Thread
import os
import requests
from datetime import date, datetime, timedelta


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, current_year


# -------------------------------------------------------------------------------------------------------------- #
# Import our classes
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, update_last_seen, logout_barred_user
from core.db_blog import Blog, create_blogs_form, STICKY, NON_STICKY, PRIVATE_NEWS, BLOG_PHOTO_FOLDER, NO_CAFE, \
                         NO_GPX, DRUNK_OPTION, CCC_OPTION
from core.dB_events import Event
from core.dB_cafes import Cafe
from core.dB_gpx import Gpx
from core.subs_blog_photos import update_blog_photo


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Show blog list
# -------------------------------------------------------------------------------------------------------------- #

@app.route("/blog", methods=['GET'])
@update_last_seen
def blog():

    # ----------------------------------------------------------- #
    # List of all news articles
    # ----------------------------------------------------------- #
    blogs = Blog().all()

    # ----------------------------------------------------------- #
    # Add some extra things for jinja
    # ----------------------------------------------------------- #
    for blog in blogs:

        # 1. Human-readable date
        if blog.date_unix:
            blog.date = datetime.utcfromtimestamp(blog.date_unix).strftime('%d %b %Y')

        # 2. Boolean for sticky
        if blog.sticky == "True":
            blog.sticky = True
        else:
            blog.sticky = False

        # 3. Boolean for Private
        if blog.privacy == PRIVATE_NEWS:
            blog.private = True
        else:
            blog.private = False

        # 4. Filenames for images
        blog.filenames = []

        if blog.images:
            indices = blog.images.split()

            for index in indices:
                filename = f"/img/blog_photos/blog_{blog.id}_{index}.jpg"

                # Check file(s) actually exist
                if os.path.exists(os.path.join(BLOG_PHOTO_FOLDER, os.path.basename(filename))):
                    print(f"Found image: {filename}")
                    blog.filenames.append(filename)

    return render_template("blog.html", year=current_year, blogs=blogs)


# -------------------------------------------------------------------------------------------------------------- #
# Add / edit a blog post
# -------------------------------------------------------------------------------------------------------------- #
@app.route("/add_blog", methods=['GET', 'POST'])
@app.route("/edit_blog", methods=['GET', 'POST'])
@update_last_seen
@logout_barred_user
@login_required
def add_blog():
    # ----------------------------------------------------------- #
    # Did we get passed a blog_id? (Optional)
    # ----------------------------------------------------------- #
    blog_id = request.args.get('blog_id', None)

    # ----------------------------------------------------------- #
    # Permissions
    # ----------------------------------------------------------- #
    if not current_user.readwrite():
        # Failed authentication
        app.logger.debug(f"add_blog(): Refusing permission for '{current_user.email}'.")
        Event().log_event("Add Blog Fail", f"Refusing permission for '{current_user.email}'.")
        flash("You do not have permission to add blog posts!")
        return abort(403)

    # ----------------------------------------------------------- #
    # Validate blog_id
    # ----------------------------------------------------------- #
    if blog_id:
        blog = Blog().find_blog_from_id(blog_id)
        if not blog:
            app.logger.debug(f"add_blog(): Failed to locate blog, blog_id = '{blog_id}'.")
            Event().log_event("Edit Blog Fail", f"Failed to locate blog, blog_id = '{blog_id}''.")
            return abort(404)
    else:
        blog = None

    # ----------------------------------------------------------- #
    # Work out what we're doing (Add / Edit)
    # ----------------------------------------------------------- #
    if blog_id \
            and request.method == 'GET':

        # ----------------------------------------------------------- #
        # Edit event, so pre-fill form from dB
        # ----------------------------------------------------------- #
        # Get a blank form
        form = create_blogs_form(current_user.admin())

        # Now fill the form in....
        form.date.data = datetime.fromtimestamp(blog.date_unix)
        form.title.data = blog.title
        form.privacy.data = blog.privacy
        form.category.data = blog.category
        if blog.cafe_id == NO_CAFE:
            form.cafe.data = NO_CAFE
        else:
            form.cafe.data = Cafe().one_cafe(blog.cafe_id).combo_string()
        if blog.gpx_index == NO_GPX:
            form.gpx.data = NO_GPX
        else:
            form.gpx.data = Gpx().one_gpx(blog.gpx_index).combo_string()
        form.details.data = blog.details

        # Admin things
        if current_user.admin():
            if blog.sticky == "True":
                form.sticky.data = STICKY
            else:
                form.sticky.data = NON_STICKY
            form.owner.data = User().find_user_from_email(blog.email).combo_str()

    else:
        # ----------------------------------------------------------- #
        # Add event, so start with fresh form
        # ----------------------------------------------------------- #
        form = create_blogs_form(current_user.admin())

        # Fill in today's date
        if request.method == 'GET':
            form.date.data = date.today()

    # Are we posting the completed comment form?
    if request.method == 'POST' \
            and form.validate_on_submit():
        # ----------------------------------------------------------- #
        # Handle form passing validation
        # ----------------------------------------------------------- #

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('blog'))

        # ----------------------------------------------------------- #
        # Validate contents
        # ----------------------------------------------------------- #
        # 1. Killjoy!
        if form.category.data == DRUNK_OPTION:
            flash("Best not post stuff when drunk!")
            return render_template("blog_new.html", year=current_year, form=form)
        elif form.category.data == CCC_OPTION:
            flash("Yep, we all know they're miserable bastards, but no need to shout about it!")
            return render_template("blog_new.html", year=current_year, form=form)

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
        new_blog.privacy = form.privacy.data
        new_blog.category = form.category.data
        new_blog.cafe_id = Cafe().cafe_id_from_combo_string(form.cafe.data)
        new_blog.gpx_index = Gpx().gpx_id_from_combo_string(form.gpx.data)
        new_blog.details = form.details.data

        # 3. Admin fields
        if current_user.admin():
            new_blog.email = User().user_from_combo_string(form.owner.data).email
            new_blog.sticky = str(form.sticky.data.lower() == STICKY.lower())
        else:
            new_blog.sticky = "False"
            new_blog.email = current_user.email

        # 4. Images
        if blog:
            # Move across existing images
            new_blog.images = blog.images

        # ----------------------------------------------------------- #
        #   Did we get passed a path for a photo?
        # ----------------------------------------------------------- #
        if form.photo_filename.data != "" and \
                form.photo_filename.data is not None:
            # Upload the photo
            update_blog_photo(form, new_blog)

        # ----------------------------------------------------------- #
        # Try and add the blog post
        # ----------------------------------------------------------- #
        new_blog = Blog().add_blog(new_blog)
        if new_blog:
            # Success
            app.logger.debug(f"add_blog(): Successfully added new blog post.")
            Event().log_event("Add Blog Pass", f"Successfully added new blog post.")
            if blog:
                flash("Blog updated!")
            else:
                flash("New Blog created!")
            return redirect(url_for('blog'))

        else:
            # Should never happen, but...
            app.logger.debug(f"add_blog(): Failed to add ride from '{new_blog}'.")
            Event().log_event("Add blog Fail", f"Failed to add ride '{new_blog}'.")
            flash("Sorry, something went wrong.")
            return render_template("blog_new.html", year=current_year, form=form)

    # ----------------------------------------------------------- #
    # Handle POST (but form validation failed)
    # ----------------------------------------------------------- #
    elif request.method == 'POST':

        # Detect cancel button
        if form.cancel.data:
            return redirect(url_for('blog'))

        # This traps a post, but where the form verification failed.
        flash("Something was missing, see comments below:")
        return render_template("blog_new.html", year=current_year, form=form)

    # ----------------------------------------------------------- #
    # Handle GET
    # ----------------------------------------------------------- #

    return render_template("blog_new.html", year=current_year, form=form)


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

    return redirect(url_for('blog'))