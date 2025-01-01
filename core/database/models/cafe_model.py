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

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(250), unique=True, nullable=False)

    # Allow cafes to be disabled (e.g. if they close) without removing from dB
    active: bool = db.Column(db.Boolean, nullable=True)

    # Need lat and lon for map locations
    lat: float = db.Column(db.Float, nullable=False)
    lon: float = db.Column(db.Float, nullable=False)

    # Optional website link and image url, which they can upload
    image_name: str = db.Column(db.String(250), nullable=True)
    website_url: str = db.Column(db.String(250), nullable=True)

    # Stick all the details in one text block
    details: str = db.Column(db.String(2000), nullable=True)
    summary: str = db.Column(db.String(100), nullable=True)
    rating: str = db.Column(db.String(100), nullable=True)

    # Who and when
    added_email: str = db.Column(db.String(250), nullable=False)

    # Added date in format "11112023"
    added_date: str = db.Column(db.String(250), nullable=False)

    # This is not used
    updated_date: str = db.Column(db.String(250), nullable=True)

    # Num routes passing cafe
    num_routes_passing: int = db.Column(db.Integer, nullable=True)

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<Blog {self.title}>'

    # ---------------------------------------------------------------------------------------------------------- #
    # Properties
    # ---------------------------------------------------------------------------------------------------------- #

    @property
    def combo_string(self) -> str:
        return f"{self.name} ({self.id})"
