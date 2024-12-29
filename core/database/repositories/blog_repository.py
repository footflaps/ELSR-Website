import os
import math
from datetime import datetime, timedelta
from enum import Enum


# -------------------------------------------------------------------------------------------------------------- #
# Import Blog Model
# -------------------------------------------------------------------------------------------------------------- #

from core import db, app
from core.database.models.blog_model import BlogModel


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Where we store blog photos
BLOG_IMAGE_FOLDER = os.environ.get('ELSR_BLOG_PHOTO_FOLDER', '/img/blog_photos/')


# Don't change these as they are in the db
class Privacy(Enum):
    PUBLIC = "Public"
    PRIVATE = "Private"


# Don't change these as they are in the db
class Sticky(Enum):
    FALSE = "Not Sticky"
    TRUE = "Sticky"


# Don't change these as they are in the db
NO_CAFE = 0
NO_GPX = 0


# Don't change these as they are in the db
class Category(Enum):
    ANNOUNCEMENT = "Announcement"
    RIDE_REPORT = "Ride Report"
    EVENT = "Event"
    NEWS = "News"
    DRUNK_OPTION = "Drunken Ramblings"
    CCC_OPTION = "Slagging off CCC"
    OTHER = "Other"


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Blog Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class BlogRepository(BlogModel):

    # ---------------------------------------------------------------------------------------------------------- #
    # Functions
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def all():
        with app.app_context():
            blogs = BlogModel.query.order_by(BlogModel.date_unix.desc()).all()
            return blogs

    @staticmethod
    def all_sticky():
        with app.app_context():
            blogs = BlogModel.query.filter_by(sticky=True).order_by(BlogModel.date_unix.desc()).all()
            return blogs

    @staticmethod
    def non_sticky(page: int, page_size: int):
        with app.app_context():
            print(f"Called with page = '{page}', page_size = '{page_size}'")
            # Get all the non-sticky blogs in time order
            # NB This is not going to be very efficient long term as we get everything, then filter it.
            # Problem is, right now we don't have our rows in time order as I'm back filling stuff at the start.
            # Over time, it will become mainly time ordered and then we can maybe filter by id, although older stuff
            # will still then appear in non-chronological order...
            blogs = BlogModel.query.filter_by(sticky=False).order_by(BlogModel.date_unix.desc())
            print(f"Found '{blogs.count()}' blog posts before pagination.")

            blogs = blogs.limit(page_size)
            print(f"Found '{blogs.count()}' blog posts after applying limit().")

            offset_val = page * page_size

            blogs = blogs.offset(offset_val)
            print(f"Found '{blogs.count()}' blog posts after applying offset({offset_val}).")

            return blogs.all()

    @staticmethod
    def number_pages(page_size):
        with app.app_context():
            num_rows = BlogModel.query.filter_by(sticky=False).count()
            return math.ceil(num_rows / page_size)

    @staticmethod
    def find_blog_from_id(blog_id):
        with app.app_context():
            blog = BlogModel.query.filter_by(id=blog_id).first()
            return blog

    @staticmethod
    def all_by_email(email):
        with app.app_context():
            blogs = BlogModel.query.filter_by(email=email).all()
            return blogs

    @staticmethod
    def all_by_date(date):
        # Need to convert calendar date string to date_unix
        try:
            date_obj = datetime(int(date[4:8]), int(date[2:4]), int(date[0:2]), 0, 00)
            date_unix = datetime.timestamp(datetime.combine(date_obj, datetime.min.time()) + timedelta(hours=2))
        except Exception as e:
            app.logger.error(f"all_by_date(): Failed to convert date = '{date}', error code '{e.args}'.")
            return []
        with app.app_context():
            blogs = BlogModel.query.filter_by(date_unix=date_unix).filter_by(category=Category.EVENT).all()
            return blogs

    @staticmethod
    def add_blog(new_blog):
        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_blog)
                db.session.commit()
                # Return blog item
                return BlogModel.query.filter_by(id=new_blog.id).first()
            except Exception as e:
                app.logger.error(f"db.add_blog(): Failed with error code '{e.args}'.")
                return None

    @staticmethod
    def delete_blog(blog_id):
        with app.app_context():
            blog = BlogModel.query.filter_by(id=blog_id).first()
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

    @staticmethod
    def update_photo(blog_id: int, filename: str):
        with app.app_context():
            blog = BlogModel.query.filter_by(id=blog_id).first()
            if blog:
                try:
                    blog.image_filename = filename
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_update_photo: Failed to update Blog for blog_id = '{blog_id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

# This seems to be the only one which works?
with app.app_context():
    db.create_all()


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
    blogs = BlogModel.query.all()
    print(f"Found {len(blogs)} blog items in the dB")
    app.logger.debug(f"Start of day: Found {len(blogs)} blogs in the dB")

