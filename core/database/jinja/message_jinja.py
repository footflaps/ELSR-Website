from core.database.repositories.message_repository import MessageRepository, ADMIN_EMAIL
from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Functions for jinja
# -------------------------------------------------------------------------------------------------------------- #

def admin_has_mail() -> bool:
    return MessageRepository.all_unread_messages_to_email(ADMIN_EMAIL)


def user_has_mail(email: str) -> bool:
    return MessageRepository.all_unread_messages_to_email(email)


app.jinja_env.globals.update(admin_has_mail=admin_has_mail)
app.jinja_env.globals.update(user_has_mail=user_has_mail)