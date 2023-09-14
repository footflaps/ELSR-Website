from flask import flash
import os



# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app,  delete_file_if_exists

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.db_blog import Blog, BLOG_PHOTO_FOLDER
from core.dB_events import Event
from core.subs_photos import shrink_image, allowed_image_files, IMAGE_ALLOWED_EXTENSIONS


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def update_blog_photo(form, blog):
    app.logger.debug(f"update_blog_photo(): Passed photo '{form.photo_filename.data.filename}'")

    if allowed_image_files(form.photo_filename.data.filename):
        # Create a new filename for the image
        filename = os.path.join(BLOG_PHOTO_FOLDER, f"blog_{blog.id}_1.jpg")
        app.logger.debug(f"update_blog_photo(): New filename for photo = '{filename}'")

        # Make sure it's not there already
        if delete_file_if_exists(filename):

            # Upload and save in our cafe photo folder
            form.photo_filename.data.save(filename)

            # Update cafe object with filename
            if Blog().update_photo(blog.id, "1"):
                # Updated ok
                app.logger.debug(f"update_blog_photo(): Successfully uploaded the photo.")
                Event().log_event("Blog Pass", f"Blog photo updated. blog.id = '{blog.id}'.")
                flash("Blog photo has been uploaded.")
            else:
                # Failed to upload eg invalid path
                app.logger.debug(f"update_blog_photo(): Failed to upload the photo '{filename}' for blog '{blog.id}'.")
                Event().log_event("Add Blog Fail", f"Couldn't upload file '{filename}' for blog '{blog.id}'.")
                flash(f"Sorry, failed to upload the file '{filename}!")

            # Shrink image if too large
            shrink_image(os.path.join(BLOG_PHOTO_FOLDER, filename))

        else:
            # Failed to delete existing file
            # NB delete_file_if_exists() will generate an error with details etc, so just flash here
            flash("Sorry, something went wrong!")

    else:
        # allowed_file() failed.
        app.logger.debug(f"update_blog_photo(): Invalid file type for image.")
        Event().log_event("Blog Fail", f"Invalid image filename '{os.path.basename(form.photo_filename.data.filename)}',"
                                       f"permitted file types are '{IMAGE_ALLOWED_EXTENSIONS}'.")
        flash("Invalid file type for image!")

