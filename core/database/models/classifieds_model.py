# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Classifieds Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class ClassifiedModel(db.Model):
    __tablename__ = 'classifieds'
    __table_args__ = {'schema': 'elsr'}

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    # Unique index number
    id = db.Column(db.Integer, primary_key=True)

    # Owner
    email = db.Column(db.String(50))

    # Date (as string)
    date = db.Column(db.String(20))

    # Title
    title = db.Column(db.String(100))

    # Type (Buy or Sell)
    buy_sell = db.Column(db.String(10))

    # Category
    category = db.Column(db.String(20))

    # CSV of filenames (no path)
    image_filenames = db.Column(db.Text)

    # Price
    price = db.Column(db.String(20))

    # Details
    details = db.Column(db.Text)

    # Status (for sale, under offer, sold, etc)
    status = db.Column(db.String(20))

    def __repr__(self):
        return f'<Classified "{self.title}, by {self.email}">'

