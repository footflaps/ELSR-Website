from datetime import date


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db
from core.database.models.cafe_comments_model import CafeCommentModel


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Cafe Comment Repository Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class CafeCommentRepository(CafeCommentModel):

    # -------------------------------------------------------------------------------------------------------------- #
    # Create
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def add_comment(new_comment: CafeCommentModel) -> bool:
        with app.app_context():
            try:
                new_comment.date = date.today().strftime("%d%m%Y")
                db.session.add(new_comment)
                db.session.commit()
                # Return success
                return True

            except Exception as e:
                db.rollback()
                app.logger.error(f"dB.add_comment(): Failed to add comment, error code was '{e.args}'.")
                return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Delete
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def delete_comment(comment_id: int) -> bool:
        with app.app_context():
            comment = CafeCommentModel.query.get(comment_id)
            # Found one?
            if comment:
                # Delete the cafe
                try:
                    db.session.delete(comment)
                    db.session.commit()
                    return True

                except Exception as e:
                    db.rollback()
                    app.logger.error(f"dB.delete_comment(): Failed to delete comment, error code was '{e.args}'.")
                    return False

        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Search
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def all() -> list[CafeCommentModel]:
        with app.app_context():
            results = CafeCommentModel.query.all()
            return results

    @staticmethod
    def get_comment(comment_id: int) -> CafeCommentModel | None:
        with app.app_context():
            comment = CafeCommentModel.query.get(comment_id)
            return comment

    # Return a list of all comments for a given cafe id
    @staticmethod
    def all_comments_by_cafe_id(cafe_id: int) -> list[CafeCommentModel]:
        with app.app_context():
            results = CafeCommentModel.query.filter_by(cafe_id=cafe_id).all()
            return results

    # Return a list of all comments for a given user email
    @staticmethod
    def all_comments_by_email(email: str) -> list[CafeCommentModel]:
        with app.app_context():
            results = CafeCommentModel.query.filter_by(email=email).all()
            return results
