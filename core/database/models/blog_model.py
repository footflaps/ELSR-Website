# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Blog Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class BlogModel(db.Model):
    __tablename__ = 'blog'
    __table_args__ = {'schema': 'elsr'}

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

    # Filename (no path) for the image
    image_filename = db.Column(db.String(30))

    # Privacy
    private = db.Column(db.Boolean)

    # Add a cafe index
    cafe_id = db.Column(db.Integer)

    # Add a gpx index
    gpx_index = db.Column(db.Integer)

    # Category
    category = db.Column(db.String(30))

    # Sticky
    sticky = db.Column(db.Boolean)

    # Details
    details = db.Column(db.Text)

    def __repr__(self):
        return f'<Blog "{self.title}, by {self.email}">'
