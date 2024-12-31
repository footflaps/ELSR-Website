from datetime import date
import json


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import db, app
from core.database.models.cafe_model import CafeModel


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

ESPRESSO_LIBRARY_INDEX = 1
BEAN_THEORY_INDEX = 65
OPEN_CAFE_ICON = "https://maps.google.com/mapfiles/ms/icons/blue-dot.png"
CLOSED_CAFE_ICON = "https://maps.google.com/mapfiles/ms/icons/red-dot.png"

OPEN_CAFE_COLOUR = "#2196f3"
CLOSED_CAFE_COLOUR = "#922b21"


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Cafe Repository Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class CafeRepository(CafeModel):

    # -------------------------------------------------------------------------------------------------------------- #
    # Create
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def add_cafe(new_cafe: CafeModel) -> CafeModel | None:
        # Update some details
        new_cafe.added_date = date.today().strftime("%d%m%Y")
        new_cafe.active = True

        # Try and add to dB
        with app.app_context():
            try:
                db.session.add(new_cafe)
                db.session.commit()
                db.session.refresh(new_cafe)
                return new_cafe

            except Exception as e:
                db.rollback()
                app.logger.error(f"dB.add_cafe(): Failed to add cafe '{new_cafe.name}', error code was '{e.args}'.")
                return None

    # -------------------------------------------------------------------------------------------------------------- #
    # Delete
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def delete_cafe(cafe_id: int) -> bool:
        with app.app_context():
            # Locate the cafe file
            cafe = CafeModel.query.filter_by(id=cafe_id).first()
            if cafe:
                # Delete the Cafe
                try:
                    db.session.delete(cafe)
                    db.session.commit()
                    return True

                except Exception as e:
                    db.rollback()
                    app.logger.error(f"db_cafe: Failed to delete Cafe for cafe_id = '{cafe_id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Modify
    # -------------------------------------------------------------------------------------------------------------- #
    # Update an existing cafe
    @staticmethod
    def update_cafe(cafe_id: int, updated_cafe: CafeModel) -> bool:
        with app.app_context():
            cafe = CafeModel.query.filter_by(id=cafe_id).first()
            if cafe:
                cafe.name = updated_cafe.name
                cafe.lat = updated_cafe.lat
                cafe.lon = updated_cafe.lon
                cafe.website_url = updated_cafe.website_url
                cafe.details = updated_cafe.details
                cafe.summary = updated_cafe.summary
                cafe.rating = updated_cafe.rating
                try:
                    db.session.commit()
                    return True

                except Exception as e:
                    db.rollback()
                    app.logger.error(f"dB.update_cafe(): Failed with cafe '{cafe.name}', error code was '{e.args}'.")
                    return False

        app.logger.error(f"dB.update_cafe(): Failed to with cafe '{cafe.name}', invalid cafe_id='{cafe_id}'.")
        return False

    @staticmethod
    def update_photo(cafe_id: int, filename: str) -> bool:
        with app.app_context():
            cafe = CafeModel.query.filter_by(id=cafe_id).first()
            if cafe:
                try:
                    cafe.image_name = filename
                    db.session.commit()
                    return True

                except Exception as e:
                    db.rollback()
                    app.logger.error(f"dB.update_photo(): Failed with cafe '{cafe.name}', error code was '{e.args}'.")
                    return False

        return False

    # Mark a cafe as being closed or closing
    @staticmethod
    def close_cafe(cafe_id: int, details: str) -> bool:
        with app.app_context():
            cafe = CafeModel.query.get(cafe_id)
            # Found one?
            if cafe:
                try:
                    # Delete the cafe
                    cafe.active = None
                    cafe.details = f"<b style='color:red'>{date.today().strftime('%d/%md/%Y')} " \
                                   f"This cafe has been marked as closed or closing: {details}</b><br>{cafe.details}"
                    db.session.commit()
                    return True

                except Exception as e:
                    db.rollback()
                    app.logger.error(f"dB.close_cafe(): Failed with cafe '{cafe.name}', error code was '{e.args}'.")
                    return False

        return False

    # Mark a cafe as no longer being closed
    @staticmethod
    def unclose_cafe(cafe_id: int) -> bool:
        with app.app_context():
            cafe = CafeModel.query.get(cafe_id)
            # Found one?
            if cafe:
                try:
                    # Delete the cafe
                    cafe.active = True
                    cafe.details = f"<b style='color:red'>{date.today().strftime('%d/%md/%Y')} " \
                                   f"Rejoice! This is no longer closing!</b><br>{cafe.details}"
                    db.session.commit()
                    return True

                except Exception as e:
                    db.rollback()
                    app.logger.error(f"dB.unclose_cafe(): Failed with cafe '{cafe.name}', error code was '{e.args}'.")
                    return False

        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Search
    # -------------------------------------------------------------------------------------------------------------- #
    # Return a list of all cafes
    @staticmethod
    def all_cafes() -> list[CafeModel]:
        with app.app_context():
            cafes = CafeModel.query.all()
            return cafes

    @staticmethod
    def all_cafes_sorted() -> list[CafeModel]:
        with app.app_context():
            cafes = CafeModel.query.order_by('name').all()
            return cafes

    # Return a single cafe
    @staticmethod
    def one_cafe(cafe_id: int) -> CafeModel | None:
        with app.app_context():
            cafe = CafeModel.query.filter_by(id=cafe_id).first()
            # Will return nothing if id is invalid
            return cafe

    @staticmethod
    def find_by_name(name: str) -> CafeModel | None:
        with app.app_context():
            cafe = CafeModel.query.filter_by(name=name).first()
            # Will return nothing if name is invalid
            return cafe

    @staticmethod
    def find_all_cafes_by_email(email) -> list[CafeModel]:
        with app.app_context():
            cafes = CafeModel.query.filter_by(added_email=email).all()
            return cafes

    # -------------------------------------------------------------------------------------------------------------- #
    # Other
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def cafe_id_from_combo_string(combo_string: str) -> int | None:
        # Extract id from number in last set of brackets
        try:
            return int(combo_string.split('(')[-1].split(')')[0])
        except Exception:
            return None

    # -------------------------------------------------------------------------------------------------------------- #
    # Properties
    # -------------------------------------------------------------------------------------------------------------- #
    def cafe_list(self, cafes_passed):
        # Take the cafe_passed JSON string from the GPX database and from it, returns the details of the
        # Cafes which were referenced in the string (referenced by id).

        cafes_json = json.loads(cafes_passed)

        # We will return this
        cafe_list = []

        for cafe_json in cafes_json:
            cafe_id = cafe_json['cafe_id']
            cafe = self.one_cafe(cafe_id)
            if cafe:
                cafe_summary = {
                    'id': cafe_id,
                    'name': cafe.name,
                    'lat': cafe.lat,
                    'lon': cafe.lon,
                    'dist_km': cafe_json['dist_km'],
                    'range_km': cafe_json['range_km'],
                    'status': cafe.active,
                }
                cafe_list.append(cafe_summary)

        return sorted(cafe_list, key=lambda x: x['range_km'])

