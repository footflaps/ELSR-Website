from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, DateField, FileField
from wtforms.validators import InputRequired, DataRequired
from flask_ckeditor import CKEditorField
import os
import math


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db, GPX_UPLOAD_FOLDER_ABS


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User
from core.dB_gpx import Gpx
from core.dB_cafes import Cafe


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Don't change these as they are in the db
PRIVATE_NEWS = "PRIVATE"
PUBLIC_NEWS = "PUBLIC"

# Don't change these as they are in the db
NO_CAFE = "NO CAFE"
NO_GPX = "NO GPX"

# Don't change these as they are in the db
DRUNK_OPTION = "Drunken Ramblings"
CCC_OPTION = "Slagging off CCC"
CATEGORIES = ["Announcement", "Ride Report", "Adventure report", "News",
              DRUNK_OPTION, CCC_OPTION, "Other"]

# Sticky options
STICKY = "Sticky"
NON_STICKY = "Not sticky"

# Where we store blog photos
BLOG_PHOTO_FOLDER = os.environ['ELSR_BLOG_PHOTO_FOLDER']


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Blog Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class Blog(db.Model):
    # We're using multiple dbs with one instance of SQLAlchemy, so have to bind to the right one.
    __bind_key__ = 'blog'

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    # Unique index number
    id = db.Column(db.Integer, primary_key=True)

    # Who created the entry - will determine delete permissions etc
    email = db.Column(db.String(50))

    # Use a unix date to make sorting by date simple
    date_unix = db.Column(db.Integer)

    # Title
    title = db.Column(db.String(50))

    # Images (list of numbers 1,2,3)
    images = db.Column(db.String(30))

    # Privacy <"Public", "Private">
    privacy = db.Column(db.String(20))

    # Add a cafe index
    cafe_id = db.Column(db.Integer)

    # Add a gpx index
    gpx_index = db.Column(db.Integer)

    # Category
    category = db.Column(db.String(30))

    # Sticky <"True", "False">
    sticky = db.Column(db.String(20))

    # Details
    details = db.Column(db.Text)

    # ---------------------------------------------------------------------------------------------------------- #
    # Functions
    # ---------------------------------------------------------------------------------------------------------- #
    def all(self):
        with app.app_context():
            blogs = db.session.query(Blog).order_by(Blog.date_unix.desc()).all()
            return blogs

    def all_sticky(self):
        with app.app_context():
            blogs = db.session.query(Blog).filter_by(sticky="True").order_by(Blog.date_unix.desc()).all()
            return blogs

    def non_sticky(self, page: int, page_size: int):
        with app.app_context():
            print(f"Called with page = '{page}', page_size = '{page_size}'")
            # Get all the non-sticky blogs in time order
            # NB This is not going to be very efficient long term as we get everything, then filter it.
            # Problem is, right now we don't have our rows in time order as I'm back filling stuff at the start.
            # Over time, it will become mainly time ordered and then we can maybe filter by id, although older stuff
            # will still then appear in non-chronological order...
            blogs = db.session.query(Blog).filter_by(sticky="False").order_by(Blog.date_unix.desc())
            print(f"Found '{blogs.count()}' blog posts before pagination.")

            blogs = blogs.limit(page_size)
            print(f"Found '{blogs.count()}' blog posts after applying limit().")

            offset_val = page * page_size

            blogs = blogs.offset(offset_val)
            print(f"Found '{blogs.count()}' blog posts after applying offset({offset_val}).")

            return blogs.all()

    def number_pages(self, page_size):
        with app.app_context():
            num_rows = db.session.query(Blog).filter_by(sticky="False").count()
            return math.ceil(num_rows / page_size)

    def find_blog_from_id(self, blog_id):
        with app.app_context():
            blog = db.session.query(Blog).filter_by(id=blog_id).first()
            return blog

    def all_by_email(self, email):
        with app.app_context():
            blogs = db.session.query(Blog).filter_by(email=email).all()
            return blogs

    def add_blog(self, new_blog):
        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_blog)
                db.session.commit()
                # Return blog item
                return db.session.query(Blog).filter_by(id=new_blog.id).first()
            except Exception as e:
                app.logger.error(f"db.add_blog(): Failed with error code '{e.args}'.")
                return None

    def delete_blog(self, blog_id):
        with app.app_context():
            blog = db.session.query(Blog).filter_by(id=blog_id).first()
            if blog:
                try:
                    db.session.delete(blog)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_delete_blog: Failed to delete Blog for blog_id = '{blog_id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    def update_photo(self, blog_id: int, filename: str):
        with app.app_context():
            blog = db.session.query(Blog).filter_by(id=blog_id).first()
            if blog:
                try:
                    blog.images = filename
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_update_photo: Failed to update Blog for blog_id = '{blog_id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    # Optional: this will allow each event object to be identified by its details when printed.
    def __repr__(self):
        return f'<Blog "{self.title}, by {self.email}">'


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

# This seems to be the only one which works?
with app.app_context():
    db.create_all()


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Forms
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

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
        cafes = Cafe().all_cafes()
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
            if gpx.public() \
                    and os.path.exists(filename):
                gpx_choices.append(gpx.combo_string())

        # ----------------------------------------------------------- #
        # The form itself
        # ----------------------------------------------------------- #

        # When
        date = DateField("Give the blog post a date:", format='%Y-%m-%d', validators=[])

        # Admin can assign to any user
        if admin:
            owner = SelectField("Owner (Admin only field):", choices=all_users,
                                validators=[InputRequired("Please enter an owner.")])

            sticky = SelectField("Sticky (Admin only field):", choices=[NON_STICKY, STICKY],
                                 validators=[InputRequired("Please enter an owner.")])

        # Title
        title = StringField("Title:", validators=[InputRequired("Please enter a title.")])

        # Privacy setting
        privacy = SelectField("Is this a private item?",choices=[PUBLIC_NEWS, PRIVATE_NEWS], validators=[])

        # Category
        category = SelectField("Category:", choices=CATEGORIES, validators=[])

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


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    blogs = db.session.query(Blog).all()
    print(f"Found {len(blogs)} blog items in the dB")
    app.logger.debug(f"Start of day: Found {len(blogs)} blogs in the dB")

