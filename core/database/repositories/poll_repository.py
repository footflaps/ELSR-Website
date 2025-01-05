# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db
from core.database.models.poll_model import PollModel


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

POLL_PRIVATE = "Private"
POLL_PUBLIC = "Public"
POLL_NO_RESPONSE = ""
POLL_OPEN = "Open"
POLL_CLOSED = "Closed"


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Poll Repository Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class PollRepository:

    # -------------------------------------------------------------------------------------------------------------- #
    # Create
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def add_poll(new_poll: PollModel) -> PollModel | None:
        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_poll)
                db.session.commit()
                db.session.refresh(new_poll)
                return new_poll

            except Exception as e:
                db.session.rollback()
                app.logger.error(f"dB.add_poll(): Failed with error code '{e.args}'.")
                print(f"dB.add_poll(): Failed with error code '{e.args}'.")
                return None

    # -------------------------------------------------------------------------------------------------------------- #
    # Delete
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def delete_poll(poll_id: int) -> bool:
        with app.app_context():

            # Locate the GPX file
            poll = PollModel.query.filter_by(id=poll_id).first()

            if poll:
                # Delete the GPX file
                try:
                    db.session.delete(poll)
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_poll: Failed to delete Poll for poll_id = '{poll_id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Search
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def all() -> list[PollModel]:
        with app.app_context():
            polls = PollModel.query.all()
            return polls

    @staticmethod
    def one_poll_by_id(poll_id: int) -> PollModel | None:
        with app.app_context():
            poll = PollModel.query.filter_by(id=poll_id).first()
            return poll
