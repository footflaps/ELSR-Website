from PIL import Image
import os

from flask import request, flash
from datetime import datetime
from typing import Optional


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Constants used for uploading images
# -------------------------------------------------------------------------------------------------------------- #

IMAGE_ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
TARGET_PHOTO_SIZE = 150000


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Permitted image file extensions
# -------------------------------------------------------------------------------------------------------------- #
def allowed_image_files(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in IMAGE_ALLOWED_EXTENSIONS


# -------------------------------------------------------------------------------------------------------------- #
# Shrink an image
# -------------------------------------------------------------------------------------------------------------- #

def shrink_image(filename):
    # Get the image size for the os
    image_size = os.path.getsize(filename)

    # Quit now if the file is already a sensible size
    if image_size <= TARGET_PHOTO_SIZE:
        app.logger.debug(f"shrink_image(): Photo '{os.path.basename(filename)}' is small enough already.")

    else:
        app.logger.debug(f"shrink_image(): Photo '{os.path.basename(filename)}' will be shrunk!")

        # Shrinkage factor (trial and error led to the method)
        scaler = (TARGET_PHOTO_SIZE / image_size)**0.45

        # Open and shrink teh image
        img = Image.open(filename)
        img = img.resize((int(img.size[0] * scaler), int(img.size[1] * scaler)))

        # Save as same file
        img.save(filename, optimize=True)


# -------------------------------------------------------------------------------------------------------------- #
# Get date from URL
# -------------------------------------------------------------------------------------------------------------- #

def get_date_from_url(return_none_if_empty: bool = False) -> Optional[str]:
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
