from flask import flash
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, delete_file_if_exists, BLOG_IMAGE_FOLDER

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.blog_repository import BlogRepository as Blog
from core.database.repositories.event_repository import EventRepository
from core.subs_photos import shrink_image, allowed_image_files, IMAGE_ALLOWED_EXTENSIONS


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# If we change a photo, we need to change the filename as well as otherwise browsers won't download the new one and
# just use the previously cached photo.
#
# The filename structure is:
#    blog_<blog_id>.jpg             for the 1st photo
#    blog_<blog_id>_<n>.jpg         for subsequent photos where n starts at 1
#
def new_blog_photo_filename(blog):
    # What are we up to...
    if not blog.image_filename:
        # First photo for this blog post
        return f"blog_{blog.id}.jpg"

    elif not os.path.exists(os.path.join(BLOG_IMAGE_FOLDER, os.path.basename(blog.image_filename))):
        # The current referenced photo isn't there, so just reset
        return f"blog_{blog.id}.jpg"

    else:
        # Already have a photo in use
        current_name = os.path.basename(blog.image_filename)

        if current_name == f"blog_{blog.id}.jpg":
            # This will be the first new photo, so start at index 1
            return f"blog_{blog.id}_1.jpg"

        else:
            # Already using indices, so need to extract index and increment by one
            try:
                # Split[2] might fail if there aren't enough '_' in the filename
                index = current_name.split('_')[2].split('.')[0]
                index = int(index) + 1
                return f"blog_{blog.id}_{index}.jpg"

            except IndexError:
                # Just reset to 1
                return f"blog_{blog.id}_1.jpg"


def update_blog_photo(form, blog):
    app.logger.debug(f"update_blog_photo(): Passed photo '{form.photo_filename.data.filename}'")

    if allowed_image_files(form.photo_filename.data.filename):
        # Create a new filename for the image
        filename = os.path.join(BLOG_IMAGE_FOLDER, new_blog_photo_filename(blog))
        app.logger.debug(f"update_blog_photo(): New filename for photo = '{filename}'")

        # Make sure it's not there already
        if delete_file_if_exists(filename):

            # Upload and save in our cafe photo folder
            form.photo_filename.data.save(filename)

            # Update cafe object with filename
            if Blog().update_photo(blog.id, f"{os.path.basename(filename)}"):
                # Updated ok
                app.logger.debug(f"update_blog_photo(): Successfully uploaded the photo.")
                EventRepository().log_event("Blog Pass", f"Blog photo updated. blog.id = '{blog.id}'.")
                flash("Blog photo has been uploaded.")
            else:
                # Failed to upload eg invalid path
                app.logger.debug(f"update_blog_photo(): Failed to upload the photo '{filename}' for blog '{blog.id}'.")
                EventRepository().log_event("Add Blog Fail", f"Couldn't upload file '{filename}' for blog '{blog.id}'.")
                flash(f"Sorry, failed to upload the file '{filename}!")

            # Shrink image if too large
            shrink_image(os.path.join(BLOG_IMAGE_FOLDER, filename))

        else:
            # Failed to delete existing file
            # NB delete_file_if_exists() will generate an error with details etc, so just flash here
            flash("Sorry, something went wrong!")

    else:
        # allowed_file() failed.
        app.logger.debug(f"update_blog_photo(): Invalid file type for image.")
        EventRepository().log_event("Blog Fail", f"Invalid image filename '{os.path.basename(form.photo_filename.data.filename)}',"
                                       f"permitted file types are '{IMAGE_ALLOWED_EXTENSIONS}'.")
        flash("Invalid file type for image!")


def delete_blog_photos(blog: Blog) -> None:
    # Check it has an id!
    if not blog.id:
        app.logger.debug(f"delete_blog_photos(): Passed blog object with no id!")
        EventRepository().log_event("Blog Fail", "delete_blog_photos(): Passed blog object with no id!")
        return

    # Delete the base name
    filename = os.path.join(BLOG_IMAGE_FOLDER, f"blog_{blog.id}.jpg")
    delete_file_if_exists(filename)

    # Now cycle through any updates
    for index in range(1, 10):
        filename = os.path.join(BLOG_IMAGE_FOLDER, f"blog_{blog.id}_{index}.jpg")
        delete_file_if_exists(filename)

