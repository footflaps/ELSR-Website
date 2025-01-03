# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Comment Model Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class CafeCommentModel(db.Model):  # type: ignore
    __tablename__ = 'cafe_comments'
    __table_args__ = {'schema': 'elsr'}

    # ---------------------------------------------------------------------------------------------------------- #
    # Define the table
    # ---------------------------------------------------------------------------------------------------------- #

    id: int = db.Column(db.Integer, primary_key=True)

    # This is the cafe.id it relates to
    cafe_id: int = db.Column(db.Integer, nullable=False)

    # When it was posted eg "11112023"
    date: str = db.Column(db.String(250), unique=False)

    # Email of user who posted it
    email: str = db.Column(db.String(100), unique=False)

    # No longer use this, instead use "get_user_name(CafeComment.email)"
    name: str = db.Column(db.String(100), unique=False)

    # Actual comments itself
    body: str = db.Column(db.String(1000), unique=False)

    # ---------------------------------------------------------------------------------------------------------- #
    # Repr
    # ---------------------------------------------------------------------------------------------------------- #

    def __repr__(self):
        return f'<Cafe comment {self.body}>'
