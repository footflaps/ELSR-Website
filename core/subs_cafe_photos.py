from flask import flash
import os
from PIL import Image


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app,  delete_file_if_exists

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.dB_cafes import Cafe
from core.dB_events import Event
from core.subs_photos import shrink_image, allowed_image_files, IMAGE_ALLOWED_EXTENSIONS


# -------------------------------------------------------------------------------------------------------------- #
# Constants used for uploading pictures of the cafes
# -------------------------------------------------------------------------------------------------------------- #

CAFE_FOLDER = os.environ['ELSR_CAFE_FOLDER']


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


def new_cafe_photo_filename(cafe):
    if not cafe.image_name:
        # First photo for this cafe
        return f"cafe_{cafe.id}.jpg"
    elif not os.path.exists(os.path.join(CAFE_FOLDER, os.path.basename(cafe.image_name))):
        # The current referenced photo isn't there, so just reset
        return f"cafe_{cafe.id}.jpg"
    else:
        # Already have a photo in use
        current_name = os.path.basename(cafe.image_name)
        # If we use the same filename the browser won't realise it's changed and just uses the cached one, so we
        # have to create a new filename.
        if current_name == f"cafe_{cafe.id}.jpg":
            # This will be the first new photo, so start at index 1
            return f"cafe_{cafe.id}_1.jpg"
        else:
            # Already using indices, so need to increment by one
            try:
                # Split[2] might fail if there aren't enough '_' in the filename
                index = current_name.split('_')[2].split('.')[0]
                index = int(index) + 1
                return f"cafe_{cafe.id}_{index}.jpg"
            except IndexError:
                # Just reset to 1
                return f"cafe_{cafe.id}_1.jpg"


def update_cafe_photo(form, cafe):
    app.logger.debug(f"update_cafe_photo(): Passed photo '{form.cafe_photo.data.filename}'")

    if allowed_image_files(form.cafe_photo.data.filename):
        # Create a new filename for the image
        filename = os.path.join(CAFE_FOLDER, new_cafe_photo_filename(cafe))
        app.logger.debug(f"update_cafe_photo(): New filename for photo = '{filename}'")

        # Make sure it's not there already
        if delete_file_if_exists(filename):

            # Upload and save in our cafe photo folder
            form.cafe_photo.data.save(filename)

            # Update cafe object with filename
            if Cafe().update_photo(cafe.id, f"{os.path.basename(filename)}"):
                # Uploaded OK
                app.logger.debug(f"update_cafe_photo(): Successfully uploaded the photo.")
                Event().log_event("Cafe Pass", f"Cafe photo updated. cafe.id = '{cafe.id}'.")
                flash("Cafe photo has been uploaded.")
            else:
                # Failed to upload eg invalid path
                app.logger.debug(f"update_cafe_photo(): Failed to upload the photo '{filename}' for cafe '{cafe.id}'.")
                Event().log_event("Add Cafe Fail", f"Couldn't upload file '{filename}' for cafe '{cafe.id}'.")
                flash(f"Sorry, failed to upload the file '{filename}!")

            # Shrink image if too large
            shrink_image(os.path.join(CAFE_FOLDER, filename))

        else:
            # Failed to delete existing file
            # NB delete_file_if_exists() will generate an error with details etc, so just flash here
            flash("Sorry, something went wrong!")

    else:
        # allowed_file() failed.
        app.logger.debug(f"update_cafe_photo(): Invalid file type for image.")
        Event().log_event("Cafe Fail", f"Invalid image filename '{os.path.basename(form.cafe_photo.data.filename)}',"
                                       f"permitted file types are '{IMAGE_ALLOWED_EXTENSIONS}'.")
        flash("Invalid file type for image!")

