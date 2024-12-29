from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField, TimeField, validators
from wtforms.validators import InputRequired
from flask_ckeditor import CKEditorField
from datetime import datetime


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.db_users import User
from core.database.repositories.db_social import SIGN_UP_CHOICES, SOCIAL_FORM_PRIVATE, SOCIAL_FORM_PUBLIC


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
    social_date = field.data
    # Convert to date object as we can't compare date vs datetime
    if type(social_date) == datetime:
        social_date = social_date.date()
    # Might not be set...
    if social_date:
        if social_date < today_date:
            raise validators.ValidationError("The date is in the past!")


# -------------------------------------------------------------------------------------------------------------- #
# Form itself
# -------------------------------------------------------------------------------------------------------------- #

def create_social_form(admin: bool):

    class Form(FlaskForm):

        # ----------------------------------------------------------- #
        # Generate the list of users
        # ----------------------------------------------------------- #
        users = User().all_users_sorted()
        all_users = []
        for user in users:
            all_users.append(user.combo_str())

        # ----------------------------------------------------------- #
        # The form itself
        # ----------------------------------------------------------- #
        date = DateField("Which day is the social for:", format='%Y-%m-%d',
                         validators=[date_validation])
        start_time = TimeField("Start time:", format="%H:%M")

        # Admin can assign to any user
        if admin:
            owner = SelectField("Owner (Admin only field):", choices=all_users,
                                validators=[InputRequired("Please enter an owner.")])

        organiser = StringField("Organiser:",
                                validators=[InputRequired("Please enter an organiser.")])

        destination = StringField("Location (can be hidden):",
                                  validators=[InputRequired("Please enter a destination.")])

        destination_hidden = SelectField("Social type:",
                                         choices=[SOCIAL_FORM_PRIVATE, SOCIAL_FORM_PUBLIC],
                                         validators=[])

        details = CKEditorField("When, where, dress code etc:",
                                validators=[InputRequired("Please provide some details.")])

        sign_up = SelectField("Do you *need* people to sign up?",
                              choices=SIGN_UP_CHOICES,
                              validators=[])

        cancel = SubmitField("Maybe not")
        submit = SubmitField("Go for it!")

    return Form()

