# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Cafe Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class CafeModel(db.Model):
    __tablename__ = 'cafes'
    __table_args__ = {'schema': 'elsr'}

    # Don't need a bind key as this is the default database
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)

    # Allow cafes to be disabled (eg if they close) without removing from dB
    active = db.Column(db.Boolean, nullable=True)

    # Need lat and lon for map locations
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)

    # Optional website link and image url, which they can upload
    image_name = db.Column(db.String(250), nullable=True)
    website_url = db.Column(db.String(250), nullable=True)

    # Stick all the details in one text block
    details = db.Column(db.String(2000), nullable=True)
    summary = db.Column(db.String(100), nullable=True)
    rating = db.Column(db.String(100), nullable=True)

    # Who and when
    added_email = db.Column(db.String(250), nullable=False)

    # Added date in format "11112023"
    added_date = db.Column(db.String(250), nullable=False)

    # This is not used
    updated_date = db.Column(db.String(250), nullable=True)

    def __repr__(self):
        return f'<Blog {self.title}>'
