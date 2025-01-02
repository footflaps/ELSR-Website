from sqlalchemy.dialects.postgresql import JSONB

# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define GPX Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class GpxModel(db.Model):  # type: ignore
    __tablename__ = 'gpx'
    __table_args__ = {'schema': 'elsr'}

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    # Primary reference
    id: int = db.Column(db.Integer, primary_key=True)

    # Filename
    filename: str = db.Column(db.String(250), unique=True, nullable=False)

    # Original target cafe (this will be a string)
    name: str = db.Column(db.String(250), nullable=False)

    # Derive stats for the file
    length_km: float = db.Column(db.Float, nullable=False)
    ascent_m: float = db.Column(db.Float, nullable=False)

    # This will be a JSON of cafe details for cafes passed
    # eg [
    #      {"cafe_id": 1, "dist_km": 0.1, "range_km": 70},
    #      {"cafe_id": 2, "dist_km": 0.2, "range_km": 30}
    #    ]
    cafes_passed: str = db.Column(db.String(3000), nullable=False)

    # Who and when uploaded it
    email: str = db.Column(db.String(250), nullable=False)

    # Date is in the format "11112023"
    date: str = db.Column(db.String(250), nullable=False)

    # Is the GPX public
    public: bool = db.Column(db.Boolean, nullable=False)

    # Type (road / off-road)
    type: str = db.Column(db.String(20))

    # Details (really just for off-road routes)
    details: str = db.Column(db.Text)

    # Number times downloaded
    downloads: str = db.Column(db.Text)

    # Clockwise, Anticlockwise or N/A
    direction: str = db.Column(db.Text)

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<GPX "{self.name}">'

    # ---------------------------------------------------------------------------------------------------------- #
    # Properties
    # ---------------------------------------------------------------------------------------------------------- #

    @property
    def combo_string(self):
        return f"{self.name}, {self.length_km}km / {self.ascent_m}m ({self.id})"

