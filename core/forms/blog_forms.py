from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField, FileField, validators
from wtforms.validators import InputRequired, DataRequired
from flask_ckeditor import CKEditorField
import os
from datetime import datetime


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import GPX_UPLOAD_FOLDER_ABS
from core.database.repositories.db_users import User
from core.database.repositories.db_gpx import Gpx
from core.database.repositories.cafes_repository import CafeRepository
from core.database.repositories.blog_repository import NO_GPX, NO_CAFE, Sticky, Privacy, Category


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Forms
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Custom validator for termination date (must be in the future)
# -------------------------------------------------------------------------------------------------------------- #
def date_validation(form, field):
    # This will be '<class 'datetime.date'>'
    today_date = datetime.today().date()
    # This can be either  '<class 'datetime.date'>' or '<class 'datetime.datetime'>'
    blog_date = field.data
    # Convert to date object as we can't compare date vs datetime
    if type(blog_date) == datetime:
        blog_date = blog_date.date()
    # Might not be set...
    if blog_date:
        if blog_date < today_date:
            raise validators.ValidationError("The date is in the past!")


def create_blogs_form(admin: bool):

    class Form(FlaskForm):

        # ----------------------------------------------------------- #
        # Generate the list of users
        # ----------------------------------------------------------- #

        users = User().all_users_sorted()
        all_users = []
        for user in users:
            all_users.append(user.combo_str())

        # ----------------------------------------------------------- #
        # Generate the list of cafes
        # ----------------------------------------------------------- #
        cafe_choices = [NO_CAFE]
        cafes = CafeRepository().all_cafes_sorted()
        for cafe in cafes:
            cafe_choices.append(cafe.combo_string())

        # ----------------------------------------------------------- #
        # Generate the list of routes
        # ----------------------------------------------------------- #
        gpx_choices = [NO_GPX]
        gpxes = Gpx().all_gpxes_sorted()
        for gpx in gpxes:
            filename = os.path.join(GPX_UPLOAD_FOLDER_ABS, os.path.basename(gpx.filename))
            # Route must be public and double check we have an actual GPX file on tap....
            if gpx.public \
                    and os.path.exists(filename):
                gpx_choices.append(gpx.combo_string())

        # ----------------------------------------------------------- #
        # The form itself
        # ----------------------------------------------------------- #

        # When
        # NB Only Admins can post events in the past
        if admin:
            date = DateField("Give the blog post a date:", format='%Y-%m-%d', validators=[])
        else:
            date = DateField("Give the blog post a date:", format='%Y-%m-%d', validators=[date_validation])

        # Admin can assign to any user
        if admin:
            owner = SelectField("Owner (Admin only field):", choices=all_users,
                                validators=[InputRequired("Please enter an owner.")])

            sticky = SelectField("Sticky (Admin only field):", choices=[e.value for e in Sticky],
                                 validators=[InputRequired("Please True or False.")])

        # Title
        title = StringField("Title:", validators=[InputRequired("Please enter a title.")])

        # Privacy setting
        privacy = SelectField("Is this a private item?", choices=[e.value for e in Privacy], validators=[])

        # Category
        category = SelectField("Category:", choices=[e.value for e in Category], validators=[])

        # Add an image
        photo_filename = FileField("Image file:", validators=[])

        # Add a cafe
        cafe = SelectField("Cafe:", choices=cafe_choices, validators=[DataRequired()])

        # Add a GPX
        gpx = SelectField("Choose an existing route:", choices=gpx_choices, validators=[DataRequired()])

        # The guts of the article
        details = CKEditorField("Spill the beans:", validators=[InputRequired("Please provide some details.")])

        # Buttons
        cancel = SubmitField("Maybe not")
        submit = SubmitField("You can do it!")

    return Form()

