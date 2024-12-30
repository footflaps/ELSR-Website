from core import app
from core.database.repositories.user_repository import UserRepository


# -------------------------------------------------------------------------------------------------------------- #
# Export some functions to jinja that we want to use inside html templates
# -------------------------------------------------------------------------------------------------------------- #

def get_user_name(user_email):
    return UserRepository().display_name(user_email)


def get_user_id_from_email(user_email):
    return UserRepository().find_id_from_email(user_email)


# Add these to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(get_user_name=get_user_name)
app.jinja_env.globals.update(get_user_id_from_email=get_user_id_from_email)
