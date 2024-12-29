from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField
from flask_ckeditor import CKEditorField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired, Length, InputRequired


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core.database.repositories.db_users import User
from core.database.repositories.db_gpx import TYPES


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Forms
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Create our upload forms
# -------------------------------------------------------------------------------------------------------------- #

class UploadGPXForm(FlaskForm):
    name = StringField("Route name eg 'Hilly route to Mill End Plants'", validators=[Length(min=6, max=50)])
    type = SelectField("Type of route:", choices=TYPES,
                       validators=[InputRequired("Please enter a type.")])
    details = CKEditorField("If gravel, add any useful details:", validators=[])
    filename = FileField("", validators=[DataRequired()])

    submit = SubmitField("Upload GPX")


# -------------------------------------------------------------------------------------------------------------- #
# Edit route name form
# -------------------------------------------------------------------------------------------------------------- #

def create_rename_gpx_form(admin: bool):

    # ----------------------------------------------------------- #
    # Generate the list of users
    # ----------------------------------------------------------- #
    users = User().all_users_sorted()
    all_users = []
    for user in users:
        all_users.append(f"{user.name} ({user.id})")

    class Form(FlaskForm):
        name = StringField("Route name eg 'Hilly route to Mill End Plants'", validators=[Length(min=6, max=50)])

        type = SelectField("Type of route:", choices=TYPES,
                           validators=[InputRequired("Please enter a type.")])

        details = CKEditorField("If gravel, add any useful details:", validators=[])

        # Admin can assign ownership
        if admin:
            owner = SelectField("Owner (Admin only field):", choices=all_users, validators=[DataRequired()])

        submit = SubmitField("Update")

    return Form()
