from datetime import date, datetime


# -------------------------------------------------------------------------------------------------------------- #
# Import out database connection from __init__
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db


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
# Define Message
# -------------------------------------------------------------------------------------------------------------- #

class Message(db.Model):
    # We're using multiple dBs with one instance of SQLAlchemy, so have to bind to the right one.
    __bind_key__ = 'messages'

    # Unique reference in dB
    id = db.Column(db.Integer, primary_key=True)

    # Contents of the message
    from_email = db.Column(db.String(250), unique=False)
    to_email = db.Column(db.String(250), unique=False)

    # Dates stored as "11112023"
    sent_date = db.Column(db.String(250), unique=False)
    read_date = db.Column(db.String(250), unique=False)

    # Actual message itself
    body = db.Column(db.String(1000), unique=False)

    # See above for details of how this works
    status = db.Column(db.Integer, unique=False)

    # ---------------------------------------------------------------------------------------------------------- #
    # Message status
    # ---------------------------------------------------------------------------------------------------------- #

    def been_read(self):
        try:
            if self.status & MASK_READ > 0:
                return True
            else:
                return False
        except TypeError:
            self.status = 0
            return False

    # ---------------------------------------------------------------------------------------------------------- #
    # Message functions
    # ---------------------------------------------------------------------------------------------------------- #

    def all_messages(self):
        with app.app_context():
            messages = db.session.query(Message).all()
            return messages

    def find_messages_by_id(self, id):
        with app.app_context():
            message = db.session.query(Message).filter_by(id=id).first()
            return message
    def all_messages_to_email(self, email):
        with app.app_context():
            messages = db.session.query(Message).filter_by(to_email=email).all()
            return messages

    def all_messages_from_email(self, email):
        with app.app_context():
            messages = db.session.query(Message).filter_by(from_email=email).all()
            return messages

    def all_unread_messages_to_email(self, email):
        with app.app_context():
            messages = db.session.query(Message).filter_by(to_email=email).all()
            unread = []
            for message in messages:
                if not message.been_read():
                    unread.append(message)
            return unread

    def add_message(self, message):
        # Add date and unread
        message.sent_date = date.today().strftime("%d%m%Y")
        message.status = NEW_MESSAGE_STATUS
        with app.app_context():
            try:
                # Update db
                db.session.add(message)
                db.session.commit()
                # Have to re-acquire the message to return it (else we get Detached Instance Error)
                return db.session.query(Message).filter_by(id=message.id).first()
            except Exception as e:
                app.logger.error(f"dB.add_message(): Failed with error code '{e.args}'.")
                return None

    def send_welcome_message(self, target_email):
        message = Message(
            from_email=ADMIN_EMAIL,
            to_email=target_email,
            body=WELCOME_MESSAGE
        )
        return self.add_message(message)

    def send_readwrite_message(self, target_email):
        message = Message(
            from_email=ADMIN_EMAIL,
            to_email=target_email,
            body=READWRITE_MESSAGE
        )
        return self.add_message(message)

    def send_readonly_message(self, target_email):
        message = Message(
            from_email=ADMIN_EMAIL,
            to_email=target_email,
            body=READONLY_MESSAGE
        )
        return self.add_message(message)

    def mark_as_read(self, id):
        with app.app_context():
            message = db.session.query(Message).filter_by(id=id).first()
            if message:
                if not message.been_read():
                    message.status += MASK_READ
                message.read_date = date.today().strftime("%d%m%Y")
                try:
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.mark_as_read(): Failed with error code '{e.args}'.")
                    return False
        return False

    def mark_as_unread(self, id):
        with app.app_context():
            message = db.session.query(Message).filter_by(id=id).first()
            if message:
                if message.been_read():
                    message.status -= MASK_READ
                message.read_date = date.today().strftime("%d%m%Y")
                try:
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.mark_as_unread(): Failed with error code '{e.args}'.")
                    return False
        return False

    def delete(self, id):
        with app.app_context():
            message = db.session.query(Message).filter_by(id=id).first()
            if message:
                try:
                    db.session.delete(message)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"dB.delete(): Failed with error code '{e.args}'.")
                    return False
        return False

    # Optional: this will allow each user object to be identified by its name when printed.
    # NB Names are not unique, but emails are, hence added in brackets
    def __repr__(self):
        return f'<Message from {self.from_email}, to {self.to_email}, on {self.sent_date}>'


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

# This one doesn't seem to work, need to use the one in the same module as the Primary dB
with app.app_context():
    db.create_all()


# -------------------------------------------------------------------------------------------------------------- #
# Functions for jinja
# -------------------------------------------------------------------------------------------------------------- #

def admin_has_mail():
    if Message().all_unread_messages_to_email(ADMIN_EMAIL):
        return True
    else:
        return False

app.jinja_env.globals.update(admin_has_mail=admin_has_mail)


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    messages = db.session.query(Message).all()
    print(f"Found {len(messages)} messages in the dB")
    app.logger.debug(f"Start of day: Found {len(messages)} messages in the dB")


# -------------------------------------------------------------------------------------------------------------- #
# Hack to change date
# -------------------------------------------------------------------------------------------------------------- #

# with app.app_context():
#     messages = Message().all_messages()
#     for message in messages:
#         if len(message.sent_date) != 8:
#             sent_date_obj = datetime.strptime(message.sent_date, "%B %d, %Y")
#             new_sent_date = sent_date_obj.strftime("%d%m%Y")
#
#             if message.read_date:
#                 read_date_obj = datetime.strptime(message.read_date, "%B %d, %Y")
#                 new_read_date = read_date_obj.strftime("%d%m%Y")
#             else:
#                 new_read_date = None
#
#             print(f"ID = {message.id}, Name = '{message.to_email}', '{message.sent_date}' -> '{new_sent_date}', "
#                   f"'{message.read_date}' -> '{new_read_date}'")
#
#             message.sent_date = new_sent_date
#             message.read_date = new_read_date
#             db.session.add(message)
#             db.session.commit()

