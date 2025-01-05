# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Classifieds Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class ClassifiedModel(db.Model):  # type: ignore
    __tablename__ = 'classifieds'
    __table_args__ = {'schema': 'elsr'}

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    # Unique index number
    id: int = db.Column(db.Integer, primary_key=True)

    # Owner
    email: str = db.Column(db.String(50))

    # Date (as string)
    date: str = db.Column(db.String(20))

    # Title
    title: str = db.Column(db.String(100))

    # Type (Buy or Sell)
    buy_sell: str = db.Column(db.String(10))

    # Category
    category: str = db.Column(db.String(20))

    # CSV of filenames (no path)
    image_filenames: str = db.Column(db.Text)

    # Price
    price: str = db.Column(db.String(20))

    # Details
    details: str = db.Column(db.Text)

    # Status (for sale, under offer, sold, etc)
    status: str = db.Column(db.String(20))

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<Classified "{self.title}, by {self.email}">'

    # ---------------------------------------------------------------------------------------------------------- #
    # Properties
    # ---------------------------------------------------------------------------------------------------------- #
    def next_photo_index(self) -> str | None:
        if self.image_filenames:
            for filename in [f"class_{self.id}_1.jpg",
                             f"class_{self.id}_2.jpg",
                             f"class_{self.id}_3.jpg",
                             f"class_{self.id}_4.jpg",
                             f"class_{self.id}_5.jpg"]:
                if filename not in self.image_filenames:
                    return filename

            return None

        else:
            # Nothing yet, so
            return f"class_{self.id}_1.jpg"
