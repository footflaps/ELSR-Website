from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, FileField
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.classifieds_repository import STATUSES, CATEGORIES, MAX_NUM_PHOTOS, DEL_IMAGE


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Forms
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

def create_classified_form(num_photos: int):

    print(f"called with num_photos = '{num_photos}'")

    class Form(FlaskForm):

        # ----------------------------------------------------------- #
        # The form itself
        # ----------------------------------------------------------- #

        # Title
        title = StringField("What are you selling:",
                            validators=[InputRequired("Please enter a title.")])

        # Status
        status = SelectField("Status:", choices=STATUSES, validators=[])

        # Category
        category = SelectField("Category:", choices=CATEGORIES, validators=[])

        # Price
        price = StringField("What is the price eg '£20 ono':",
                            validators=[InputRequired("You must give a price.")])

        # Product details
        details = CKEditorField("Describe the item (the more detail the better):",
                                validators=[InputRequired("Please provide some details.")])

        if num_photos > 4:
            # Add image #1
            photo_filename_1 = FileField("1st image file:", validators=[])
        else:
            del_image_1 = SelectField(f"Delete 1st image of {MAX_NUM_PHOTOS - num_photos} already used:",
                                      choices=DEL_IMAGE, validators=[])

        if num_photos > 3:
            # Add image #2
            photo_filename_2 = FileField("2nd image file:", validators=[])
        else:
            del_image_2 = SelectField(f"Delete 2nd image of {MAX_NUM_PHOTOS - num_photos} already used:",
                                      choices=DEL_IMAGE, validators=[])

        if num_photos > 2:
            # Add image #3
            photo_filename_3 = FileField("3rd image file:", validators=[])
        else:
            del_image_3 = SelectField(f"Delete 3rd image of {MAX_NUM_PHOTOS - num_photos} already used:",
                                      choices=DEL_IMAGE, validators=[])

        if num_photos > 1:
            # Add image #4
            photo_filename_4 = FileField("4th image file:", validators=[])
        else:
            del_image_4 = SelectField(f"Delete 4th image of {MAX_NUM_PHOTOS - num_photos} already used:",
                                      choices=DEL_IMAGE, validators=[])

        if num_photos > 0:
            # Add image #5
            photo_filename_5 = FileField("5th image file:", validators=[])
        else:
            del_image_5 = SelectField(f"Delete 5th image of {MAX_NUM_PHOTOS - num_photos} already used:",
                                      choices=DEL_IMAGE, validators=[])

        # Buttons
        cancel = SubmitField("Maybe not")
        submit = SubmitField("Sell it all now!")

    return Form()
