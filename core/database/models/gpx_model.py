# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# Define GPX Class
# -------------------------------------------------------------------------------------------------------------- #

class GpxModel(db.Model):
    __tablename__ = 'gpx'
    __table_args__ = {'schema': 'elsr'}

    # Primary reference
    id = db.Column(db.Integer, primary_key=True)

    # Filename
    filename = db.Column(db.String(250), unique=True, nullable=False)

    # Original target cafe (this will be a string)
    name = db.Column(db.String(250), nullable=False)

    # Derive stats for the file
    length_km = db.Column(db.Float, nullable=False)
    ascent_m = db.Column(db.Float, nullable=False)

    # This will be a JSON of cafe details for cafes passed
    # eg [
    #      {"cafe_id": 1, "dist_km": 0.1, "range_km": 70},
    #      {"cafe_id": 2, "dist_km": 0.2, "range_km": 30}
    #    ]
    cafes_passed = db.Column(db.String(3000), nullable=False)

    # Who and when uploaded it
    email = db.Column(db.String(250), nullable=False)

    # Date is in the format "11112023"
    date = db.Column(db.String(250), nullable=False)

    # Is the GPX valid
    valid = db.Column(db.Integer, nullable=True)

    # Type (road / offroad)
    type = db.Column(db.String(20))

    # Details (really just for offroad routes)
    details = db.Column(db.Text)

    # Number times downloaded
    downloads = db.Column(db.Text)

    # Clockwise, Anticlockwise or N/A
    direction = db.Column(db.Text)

    def __repr__(self):
        return f'<GPX "{self.name}">'

