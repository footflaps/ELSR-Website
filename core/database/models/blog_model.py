from datetime import date

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
    id: int = db.Column(db.Integer, primary_key=True)

    # Who created the entry - will determine delete permissions etc
    email: str = db.Column(db.String(50))

    # Use a unix date to make sorting by date simple
    date_unix: int = db.Column(db.Integer)

    # New date column using a proper SQL Date field
    converted_date: date = db.Column(db.Date)

    # Title
    title: str = db.Column(db.String(50))

    # Filename (no path) for the image
    image_filename: str = db.Column(db.String(30))

    # Privacy
    private: bool = db.Column(db.Boolean)

    # Add a cafe index
    cafe_id: int = db.Column(db.Integer)

    # Add a gpx index
    gpx_index: int = db.Column(db.Integer)

    # Category
    category: str = db.Column(db.String(30))

    # Sticky
    sticky: bool = db.Column(db.Boolean)

    # Details
    details: str = db.Column(db.Text)

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<Blog "{self.title}, by {self.email}">'
