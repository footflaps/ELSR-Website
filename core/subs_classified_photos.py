from flask import flash
import os


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, CLASSIFIEDS_PHOTO_FOLDER, delete_file_if_exists

# -------------------------------------------------------------------------------------------------------------- #
# Import our three database classes and associated forms, decorators etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.classified_repository import ClassifiedRepository, DELETE_PHOTO
from core.database.repositories.event_repository import EventRepository
from core.subs_photos import shrink_image, allowed_image_files, IMAGE_ALLOWED_EXTENSIONS


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Handle selective image deletion from form
# -------------------------------------------------------------------------------------------------------------- #
def delete_classifieds_photos(classified, form):
    # ----------------------------------------------------------- #
    # Loop through the image filenames in the classified object
    # ----------------------------------------------------------- #
    # Might not be set eg Null
    if classified.image_filenames:

        count = 0
        image_names = ""

        # Parse as CSV string
        for image_name in classified.image_filenames.split(','):

            count += 1

            # Strings of single spaces seem to pass for some reason, so exclude them
            if image_name.strip() != "":

                # Get absolute path
                filename = os.path.join(CLASSIFIEDS_PHOTO_FOLDER, os.path.basename(image_name))

                print(f"Inspecting '{filename}'")

                photo_deleted = False

                # Do they want to delete this image?
                if count == 1:
                    try:
                        if form.del_image_1.data == DELETE_PHOTO:
                            # Delete photo
                            delete_file_if_exists(filename)
                            photo_deleted = True
                    except:
                        pass

                elif count == 2:
                    try:
                        if form.del_image_2.data == DELETE_PHOTO:
                            # Delete photo
                            delete_file_if_exists(filename)
                            photo_deleted = True
                    except:
                        pass

                elif count == 3:
                    try:
                        if form.del_image_3.data == DELETE_PHOTO:
                            # Delete photo
                            delete_file_if_exists(filename)
                            photo_deleted = True
                    except:
                        pass

                elif count == 4:
                    try:
                        if form.del_image_4.data == DELETE_PHOTO:
                            # Delete photo
                            delete_file_if_exists(filename)
                            photo_deleted = True
                    except:
                        pass

                elif count ==5:
                    try:
                        if form.del_image_5.data == DELETE_PHOTO:
                            # Delete photo
                            delete_file_if_exists(filename)
                            photo_deleted = True
                    except:
                        pass

                # Keep the image name if we're keeping the photo
                if not photo_deleted:
                    image_names = image_names + image_name + ","

        # Update list of images
        classified.image_filenames = image_names


# -------------------------------------------------------------------------------------------------------------- #
# Remove all photos (when deleting a post)
# -------------------------------------------------------------------------------------------------------------- #
def delete_all_classified_photos(classified):
    # ----------------------------------------------------------- #
    # Loop through the image filenames in the classified object
    # ----------------------------------------------------------- #
    # Might not be set eg Null
    if classified.image_filenames:

        # Parse as CSV string
        for image_name in classified.image_filenames.split(','):

            # Strings of single spaces seem to pass for some reason, so exclude them
            if image_name.strip() != "":

                # Get absolute path
                filename = os.path.join(CLASSIFIEDS_PHOTO_FOLDER, os.path.basename(image_name))

                # Delete
                delete_file_if_exists(filename)


# -------------------------------------------------------------------------------------------------------------- #
# Upload a set of photos from the form
# -------------------------------------------------------------------------------------------------------------- #

def add_classified_photos(classified, form):
    # Forms are dynamic and may or may not have each field
    try:
        if form.photo_filename_1.data.filename != "":
            add_one_classified_photo(classified, form.photo_filename_1.data)
    except AttributeError:
        pass

    # Forms are dynamic and may or may not have each field
    try:
        if form.photo_filename_2.data.filename != "":
            add_one_classified_photo(classified, form.photo_filename_2.data)
    except AttributeError:
        pass

    # Forms are dynamic and may or may not have each field
    try:
        if form.photo_filename_3.data.filename != "":
            add_one_classified_photo(classified, form.photo_filename_3.data)
    except AttributeError:
        pass

    # Forms are dynamic and may or may not have each field
    try:
        if form.photo_filename_4.data.filename != "":
            add_one_classified_photo(classified, form.photo_filename_4.data)
    except AttributeError:
        pass

    # Forms are dynamic and may or may not have each field
    try:
        if form.photo_filename_5.data.filename != "":
            add_one_classified_photo(classified, form.photo_filename_5.data)
    except AttributeError:
        pass


# -------------------------------------------------------------------------------------------------------------- #
# Upload a single photo
# -------------------------------------------------------------------------------------------------------------- #

def add_one_classified_photo(classified, form_data):
    # Get the filename on the user's machine
    upload_filename = form_data.filename
    print(f"add_one_classified_photo(): Passed photo '{upload_filename}'")
    app.logger.debug(f"add_one_classified_photo(): Passed photo '{upload_filename}'")

    # We only allow .jpg and .jpeg etc
    if allowed_image_files(upload_filename):
        # Need the next free index number for this photo
        local_filename = classified.next_photo_index()

        # Check we got something back
        if not local_filename:
            # Should never happen, but....
            app.logger.debug(f"add_one_classified_photo(): Failed to get local filename, "
                             f"classified.id = '{classified.id}'.")
            EventRepository().log_event("Classified Photo Fail", f"Failed to get local filename, "
                                                       f"classified.id = '{classified.id}'.")
            flash(f"Sorry, failed to upload the file '{upload_filename}!")
            # Just abort
            return

        # Create a filename for the image on the server
        local_filename = os.path.join(CLASSIFIEDS_PHOTO_FOLDER, local_filename)
        app.logger.debug(f"add_one_classified_photo(): New filename for photo = '{local_filename}'")

        # Make sure it's not there already
        if delete_file_if_exists(local_filename):

            # Upload and save in our cafe photo folder
            form_data.save(local_filename)

            # Update Classified object with filename
            if classified.image_filenames:
                classified.image_filenames += f",{os.path.basename(local_filename)}"
            else:
                classified.image_filenames = f"{os.path.basename(local_filename)}"

            # Shrink image if too large
            shrink_image(os.path.join(CLASSIFIEDS_PHOTO_FOLDER, local_filename))

        else:
            # Failed to delete existing file
            # NB delete_file_if_exists() will generate an error with details etc, so just flash here
            flash("Sorry, something went wrong!")

    else:
        # allowed_file() failed.
        app.logger.debug(f"add_one_classified_photo(): Invalid file type for image.")
        EventRepository().log_event("Classified Photo Fail",
                          f"Invalid image filename '{os.path.basename(upload_filename)}',"
                          f"permitted file types are '{IMAGE_ALLOWED_EXTENSIONS}'.")
        flash("Invalid file type for image!")
