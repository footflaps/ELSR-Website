from core import app
import re
from core.database.repositories.cafes_repository import CafeRepository


def remove_html_tags(text):
    """Remove html tags from a string"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


# Pass this to jinja
app.jinja_env.globals.update(remove_html_tags=remove_html_tags)


def get_cafe_name_from_id(cafe_id):
    return CafeRepository().one_cafe(cafe_id).name


# Add this to jinja's environment, so we can use it within html templates
app.jinja_env.globals.update(get_cafe_name_from_id=get_cafe_name_from_id)
