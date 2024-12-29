from flask_ckeditor import CKEditorField
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, SelectField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired


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

class CreateCafeForm(FlaskForm):
    name = StringField("Cafe name", validators=[DataRequired()])
    lat = FloatField("Latitude", validators=[DataRequired()])
    lon = FloatField("Longitude", validators=[DataRequired()])
    website_url = StringField("Website URL", validators=[])
    summary = StringField("Five word summary", validators=[DataRequired()])
    rating = SelectField("Overall rating for a cycling cafe ride",
                         choices=["☕️", "☕☕", "☕☕☕", "☕☕☕☕", "☕☕☕☕☕"],
                         validators=[DataRequired()])
    cafe_photo = FileField("Image file for the cafe.", validators=[])

    # Use the full feature editor for the details section
    detail = CKEditorField("Details", validators=[DataRequired()])

    submit = SubmitField("Submit")

