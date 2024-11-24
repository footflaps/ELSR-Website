from flask_ckeditor import CKEditorField
from flask_wtf import FlaskForm
from wtforms import SubmitField
from wtforms.validators import DataRequired
from datetime import date, datetime
import re


# -------------------------------------------------------------------------------------------------------------- #
# Import out database connection from __init__
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db


# -------------------------------------------------------------------------------------------------------------- #
# Define Comment
# -------------------------------------------------------------------------------------------------------------- #

class CafeComment(db.Model):
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

    def all(self):
        with app.app_context():
            comments = db.session.query(CafeComment).all()
            return comments

    # Add a new comment
    def add_comment(self, new_comment):
        with app.app_context():
            try:
                new_comment.date = date.today().strftime("%d%m%Y")
                db.session.add(new_comment)
                db.session.commit()
                # Return success
                return True
            except Exception as e:
                app.logger.error(f"dB.add_comment(): Failed to add comment, error code was '{e.args}'.")
                return False

    # Delete a comment
    def delete_comment(self, comment_id):
        with app.app_context():
            comment = db.session.query(CafeComment).get(comment_id)
            # Found one?
            if comment:
                # Delete the cafe
                try:
                    db.session.delete(comment)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.delete_comment(): Failed to delete comment, error code was '{e.args}'.")
                    return False
        return False

    def get_comment(self, comment_id):
        with app.app_context():
            comment = db.session.query(CafeComment).get(comment_id)
            return comment

    # Return a list of all comments for a given cafe id
    def all_comments_by_cafe_id(self, cafe_id):
        with app.app_context():
            comments = db.session.query(CafeComment).filter_by(cafe_id=cafe_id).all()
            return comments

    # Return a list of all comments for a given user email
    def all_comments_by_email(self, email):
        with app.app_context():
            comments = db.session.query(CafeComment).filter_by(email=email).all()
            return comments

    # Optional: this will allow each blog object to be identified by its name when printed.
    def __repr__(self):
        return f'<Cafe comment {self.body}>'


# -------------------------------------------------------------------------------------------------------------- #
# Create user comment form
# -------------------------------------------------------------------------------------------------------------- #

class CreateCafeCommentForm(FlaskForm):
    # Use the full feature editor for the comment
    body = CKEditorField("Comments should be polite and helpful!", validators=[DataRequired()])
    submit = SubmitField("Submit")


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

# This one doesn't seem to work, need to use the one in the same module as the Primary dB
with app.app_context():
    db.create_all()


# -------------------------------------------------------------------------------------------------------------- #
# If we want to strip html from comments
# -------------------------------------------------------------------------------------------------------------- #

def remove_html_tags(text):
    """Remove html tags from a string"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


# Pass this to jinja
app.jinja_env.globals.update(remove_html_tags=remove_html_tags)


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    comments = db.session.query(CafeComment).all()
    print(f"Found {len(comments)} comments in the dB")
    app.logger.debug(f"Start of day: Found {len(comments)} comments in the dB")


# -------------------------------------------------------------------------------------------------------------- #
# Hack to change date and name
# -------------------------------------------------------------------------------------------------------------- #

# with app.app_context():
#     comments = CafeComment().all()
#     for comment in comments:
#         if comment.name:
#             date_obj = datetime.strptime(comment.date, "%B %d, %Y")
#             new_date = date_obj.strftime("%d%m%Y")
#             print(f"ID = {comment.id}, Name = '{comment.name}', Date = '{comment.date}' or '{new_date}'")
#             comment.date = new_date
#             comment.name = None
#             db.session.add(comment)
#             db.session.commit()

