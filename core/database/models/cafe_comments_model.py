# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import db


# -------------------------------------------------------------------------------------------------------------- #
# Define Comment
# -------------------------------------------------------------------------------------------------------------- #

class CafeCommentModel(db.Model):
    __tablename__ = 'cafe_comments'
    __table_args__ = {'schema': 'elsr'}

    id = db.Column(db.Integer, primary_key=True)

    # This is the cafe.id it relates to
    cafe_id = db.Column(db.Integer, nullable=False)

    # When it was posted eg "11112023"
    date = db.Column(db.String(250), unique=False)

    # Email of user who posted it
    email = db.Column(db.String(100), unique=False)

    # No longer use this, instead use "get_user_name(CafeComment.email)"
    name = db.Column(db.String(100), unique=False)

    # Actual comments itself
    body = db.Column(db.String(1000), unique=False)

    def __repr__(self):
        return f'<Cafe comment {self.body}>'
