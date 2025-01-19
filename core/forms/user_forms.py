from flask_wtf import FlaskForm
from flask_ckeditor import CKEditorField
from wtforms import StringField, EmailField, SubmitField, PasswordField, IntegerField, URLField, SelectField, validators
from wtforms.validators import InputRequired, Email
from validators import url as check_url


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import GROUP_CHOICES
from core.database.repositories.user_repository import SIZES


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Forms
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Create User Registration form
# -------------------------------------------------------------------------------------------------------------- #
class CreateUserForm(FlaskForm):
    name = StringField("Name (this will appear on the website)",
                       validators=[InputRequired("Please enter your name.")])
    email = EmailField("Email address (this will be kept hidden)",
                       validators=[InputRequired("Please enter your email address."), Email()])
    password = PasswordField("Password",
                             validators=[InputRequired("Please enter a password.")])
    submit = SubmitField("Register")


# -------------------------------------------------------------------------------------------------------------- #
# Verify User email form
# -------------------------------------------------------------------------------------------------------------- #
class VerifyUserForm(FlaskForm):
    email = EmailField("Email address",
                       validators=[InputRequired("Please enter your email address."), Email()])
    verification_code = IntegerField("Verification code",
                                     validators=[InputRequired("Please enter the six digit code emailed to you.")])
    submit = SubmitField("Verify email address")


# -------------------------------------------------------------------------------------------------------------- #
# Verify User SMS form
# -------------------------------------------------------------------------------------------------------------- #
class TwoFactorLoginForm(FlaskForm):
    email = EmailField("Email address",
                       validators=[InputRequired("Please enter your email address."), Email()])
    verification_code = IntegerField("Verification code",
                                     validators=[InputRequired("Please enter the six digit code SMSed to you.")])
    submit = SubmitField("2FA Login")


# -------------------------------------------------------------------------------------------------------------- #
# Verify User SMS form
# -------------------------------------------------------------------------------------------------------------- #
class VerifySMSForm(FlaskForm):
    verification_code = IntegerField("Verification code",
                                     validators=[InputRequired("Please enter the six digit code SMSed to you.")])
    submit = SubmitField("Verify Mobile")


# -------------------------------------------------------------------------------------------------------------- #
# Login User form
# -------------------------------------------------------------------------------------------------------------- #
class LoginUserForm(FlaskForm):
    email = EmailField("Email address",
                       validators=[InputRequired("Please enter your email address."), Email()])
    # Don't require a password in the form as they might have forgotten it...
    password = PasswordField("Password")

    # Two buttons, Log in and I've forgotten my password...
    submit = SubmitField("Log in")
    forgot = SubmitField("Reset Password")
    verify = SubmitField("re-send Verification Code")


# -------------------------------------------------------------------------------------------------------------- #
# Reset Password form
# -------------------------------------------------------------------------------------------------------------- #
class ResetPasswordForm(FlaskForm):
    email = EmailField("Email address", validators=[InputRequired("Please enter your email address.")])
    reset_code = IntegerField("Reset code", validators=[InputRequired("Please enter your reset code.")])
    password1 = PasswordField("Password", validators=[InputRequired("Please enter a password.")])
    password2 = PasswordField("Password again", validators=[InputRequired("Please enter a password.")])
    submit = SubmitField("Reset password")


# -------------------------------------------------------------------------------------------------------------- #
# Custom validator for URLs (which accepts a blank field)
# -------------------------------------------------------------------------------------------------------------- #
def url_validation(form, field):
    if field.data.strip() != "" and \
         not check_url(field.data):
        raise validators.ValidationError('This is not a valid url eg https://www.strava.com/')


# -------------------------------------------------------------------------------------------------------------- #
# User details form
# -------------------------------------------------------------------------------------------------------------- #
class ChangeUserDetailsForm(FlaskForm):
    name = StringField("Change user name:", validators=[InputRequired("Please enter your name.")])
    bio = CKEditorField("Witty one liner:", validators=[])
    groups = GROUP_CHOICES.copy()
    groups.insert(0, "n/a")
    group = SelectField("Main Group:", choices=groups)
    strava = URLField("Strava url:", validators=[url_validation])
    instagram = URLField("Instagram url:", validators=[url_validation])
    twitter = URLField("Twitter / X url:", validators=[url_validation])
    facebook = URLField("Facebook url:", validators=[url_validation])
    emergency = CKEditorField("Emergency Contact Details (number, relationship, etc):", validators=[])
    submit = SubmitField("Update me!")


# -------------------------------------------------------------------------------------------------------------- #
# Clothing size form
# -------------------------------------------------------------------------------------------------------------- #
class ClothingSizesForm(FlaskForm):
    jersey_ss_relaxed = SelectField("Sunny Day (relaxed fit) SS Jersey:", choices=SIZES)
    jersey_ss_race = SelectField("Hard Day (race fit) SS Jersey:", choices=SIZES)
    jersey_ls = SelectField("Long Sleeve Jersey:", choices=SIZES)
    gilet = SelectField("Gilet:", choices=SIZES)
    bib_shorts = SelectField("Bib shorts:", choices=SIZES)
    bib_longs = SelectField("Bib longs:", choices=SIZES)
    notes = CKEditorField("Notes:", validators=[])
    submit = SubmitField("Save me!")

