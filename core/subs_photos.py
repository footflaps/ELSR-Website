from PIL import Image
import os


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

