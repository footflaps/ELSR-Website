# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db
from core.database.models.polls_model import PollsModel


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
# Define Poll Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class Polls(PollsModel):

    def all(self):
        with app.app_context():
            polls = db.session.query(Polls).all()
            return polls

    def one_poll_by_id(self, poll_id):
        with app.app_context():
            poll = db.session.query(Polls).filter_by(id=poll_id).first()
            return poll

    def add_poll(self, new_poll):
        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_poll)
                db.session.commit()
                # Return social object
                return db.session.query(Polls).filter_by(id=new_poll.id).first()
            except Exception as e:
                app.logger.error(f"dB.add_poll(): Failed with error code '{e.args}'.")
                print(f"EdB.add_poll(): Failed with error code '{e.args}'.")
                return None

    def delete_poll(self, poll_id):
        with app.app_context():

            # Locate the GPX file
            poll = db.session.query(Polls).filter_by(id=poll_id).first()

            if poll:
                # Delete the GPX file
                try:
                    db.session.delete(poll)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_poll: Failed to delete Poll for poll_id = '{poll_id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    db.create_all()


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
#                                               Functions
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    polls = db.session.query(Polls).all()
    print(f"Found {len(polls)} polls in the dB")
    app.logger.debug(f"Start of day: Found {len(polls)} polls in the dB")
