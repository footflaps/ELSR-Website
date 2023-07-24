from flask import current_app
from flask_ckeditor import CKEditorField
from flask_wtf import FlaskForm
from wtforms import SubmitField
from wtforms.validators import DataRequired
from datetime import date
import re


# -------------------------------------------------------------------------------------------------------------- #
# Import out database connection from __init__
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db


# -------------------------------------------------------------------------------------------------------------- #
# Define Comment
# -------------------------------------------------------------------------------------------------------------- #

class CafeComment(db.Model):
    # We're using multiple dBs with one instance of SQLAlchemy, so have to bind to the right one.
    __bind_key__ = 'cafe_comments'

    id = db.Column(db.Integer, primary_key=True)
    # Which article does it refer to (use id)
    article_id = db.Column(db.Integer, nullable=False)
    # When it was posted
    date = db.Column(db.String(250), unique=False)
    # Who posted it - use email and user name rather than id (as they could leave)
    email = db.Column(db.String(100), unique=False)
    name = db.Column(db.String(100), unique=False)
    # Actual comments itself
    body = db.Column(db.String(1000), unique=False)

    # Add a new comment
    def add_comment(self, new_comment):
        with app.app_context():
            try:
                new_comment.date = date.today().strftime("%B %d, %Y")
                db.session.add(new_comment)
                db.session.commit()
                # Return success
                return True
            except Exception as e:
                print(f"db_cafe_comment: Failed to add comment {new_comment}, error code was {e.args}.")
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
                    print(f"db_cafe_comment: Failed to delete comment {comment}, error code was {e.args}.")
                    return False
        return False

    def get_comment(self, comment_id):
        with app.app_context():
            comment = db.session.query(CafeComment).get(comment_id)
            return comment

    # Return a list of all comments for a given cafe id
    def all_comments_by_id(self, article_id):
        with app.app_context():
            comments = db.session.query(CafeComment).filter_by(article_id=article_id).all()
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
    submit = SubmitField("Submit Comment")


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