from core.database.repositories.message_repository import MessageRepository, ADMIN_EMAIL
from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Functions for jinja
# -------------------------------------------------------------------------------------------------------------- #

def admin_has_mail():
    if MessageRepository().all_unread_messages_to_email(ADMIN_EMAIL):
        return True
    else:
        return False


app.jinja_env.globals.update(admin_has_mail=admin_has_mail)
