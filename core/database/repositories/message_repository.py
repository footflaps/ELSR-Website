from datetime import date


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db
from core.database.models.message_model import MessageModel


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Message().status is an Integer value with binary breakdown:
#       1 :     Read                    1 = Read,           0 = Not been read
#       2 :     TBD                     1 = ,               0 =
#       4 :     TBD                     1 = ,               0 =

# Use these masks on the Integer to extract permissions
MASK_READ = 1

NEW_MESSAGE_STATUS = 0

ADMIN_EMAIL = "Admin"

WELCOME_MESSAGE = "Welcome to the new ELSR website. Now you have registered you can download GPX files. Once " \
                  "an admin has verified your identity, you will receive write permissions and be able to add and " \
                  "edit content."

READWRITE_MESSAGE = "Congratulations, the Admin team have now given you read and write permissions. You can now add " \
                    "and edit content on the site, e.g. organise rides and add events to the Calendar. There is also " \
                    "a link to join our WhatsApp group on your user page."

READONLY_MESSAGE = "Sorry, but the Admins have removed your write permissions to the site."


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Message Repository Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class MessageRepository:

    # ---------------------------------------------------------------------------------------------------------- #
    # Create
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def add_message(message: MessageModel) -> MessageModel | None:
        # Add date and unread
        message.sent_date = date.today().strftime("%d%m%Y")
        message.status = NEW_MESSAGE_STATUS
        with app.app_context():
            try:
                # Update db
                db.session.add(message)
                db.session.commit()
                db.session.refresh(message)
                return message

            except Exception as e:
                db.session.rollback()
                app.logger.error(f"dB.add_message(): Failed with error code '{e.args}'.")
                return None

    # ---------------------------------------------------------------------------------------------------------- #
    # Modify
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def mark_as_read(id: int) -> bool:
        with app.app_context():
            message = MessageModel.query.filter_by(id=id).first()
            if message:
                if not message.been_read:
                    message.status += MASK_READ
                message.read_date = date.today().strftime("%d%m%Y")
                try:
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"dB.mark_as_read(): Failed with error code '{e.args}'.")
                    return False

        return False

    @staticmethod
    def mark_as_unread(id: int) -> bool:
        with app.app_context():
            message = MessageModel.query.filter_by(id=id).first()
            if message:
                if message.been_read:
                    message.status -= MASK_READ
                message.read_date = date.today().strftime("%d%m%Y")
                try:
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"dB.mark_as_unread(): Failed with error code '{e.args}'.")
                    return False

        return False

    # ---------------------------------------------------------------------------------------------------------- #
    # Delete
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def delete(id: int) -> bool:
        with app.app_context():
            message = MessageModel.query.filter_by(id=id).first()
            if message:
                try:
                    db.session.delete(message)
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"dB.delete(): Failed with error code '{e.args}'.")
                    return False

        return False

    # ---------------------------------------------------------------------------------------------------------- #
    # Search
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def all_messages() -> list[MessageModel]:
        with app.app_context():
            messages = MessageModel.query.all()
            return messages

    @staticmethod
    def find_messages_by_id(id: int) -> MessageModel | None:
        with app.app_context():
            message = MessageModel.query.filter_by(id=id).first()
            return message

    @staticmethod
    def all_messages_to_email(email: str) -> list[MessageModel]:
        with app.app_context():
            messages = MessageModel.query.filter_by(to_email=email).all()
            return messages

    @staticmethod
    def all_messages_from_email(email: str) -> list[MessageModel]:
        with app.app_context():
            messages = MessageModel.query.filter_by(from_email=email).all()
            return messages

    @staticmethod
    def all_unread_messages_to_email(email: str) -> list[MessageModel]:
        with app.app_context():
            messages = MessageModel.query.filter_by(to_email=email).filter(MessageModel.status.op('&')(MASK_READ) == 0) .all()
            return messages

    # ---------------------------------------------------------------------------------------------------------- #
    # Other
    # ---------------------------------------------------------------------------------------------------------- #
    @classmethod
    def send_welcome_message(cls, target_email: str) -> MessageModel | None:
        message = MessageModel(
            from_email=ADMIN_EMAIL,
            to_email=target_email,
            body=WELCOME_MESSAGE
        )
        return cls.add_message(message)

    @classmethod
    def send_readwrite_message(cls, target_email: str) -> MessageModel | None:
        message = MessageModel(
            from_email=ADMIN_EMAIL,
            to_email=target_email,
            body=READWRITE_MESSAGE
        )
        return cls.add_message(message)

    @classmethod
    def send_readonly_message(cls, target_email: str) -> MessageModel | None:
        message = MessageModel(
            from_email=ADMIN_EMAIL,
            to_email=target_email,
            body=READONLY_MESSAGE
        )
        return cls.add_message(message)
