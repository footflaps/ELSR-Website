from datetime import date


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

WELCOME_MESSAGE = "Welcome to the new elsr.co.uk website. Now you have registered you can add to the cafe list, " \
                  "upload GPX files and download GPX files. If you find something amiss or broken, you can contact " \
                  "an admin using the internal messaging system."

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
    sent_date = db.Column(db.String(250), unique=False)
    read_date = db.Column(db.String(250), unique=False)
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
        message.sent_date = date.today().strftime("%B %d, %Y")
        message.status = NEW_MESSAGE_STATUS
        with app.app_context():
            try:
                db.session.add(message)
                db.session.commit()
                # Return success
                return True
            except Exception as e:
                app.logger.error(f"dB.add_message(): Failed with error code '{e.args}'.")
                return False

    def send_welcome_message(self, target_email):
        message = Message(
            from_email=ADMIN_EMAIL,
            to_email=target_email,
            body=WELCOME_MESSAGE
        )
        return self.add_message(message)

    def mark_as_read(self, id):
        with app.app_context():
            message = db.session.query(Message).filter_by(id=id).first()
            if message:
                if not message.been_read():
                    message.status += MASK_READ
                message.read_date = date.today().strftime("%B %d, %Y")
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
                message.read_date = date.today().strftime("%B %d, %Y")
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