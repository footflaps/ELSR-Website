from core import app
from core.database.repositories.gpx_repository import GpxRepository
from core.database.models.user_model import UserModel


def number_routes_passing_by(cafe_id: id, user: UserModel) -> int:
    routes = GpxRepository().find_all_gpx_for_cafe(cafe_id, user)
    return len(routes)


# Add it to Jinja2's globals
app.jinja_env.globals.update(number_routes_passing_by=number_routes_passing_by)
