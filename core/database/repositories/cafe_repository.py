from datetime import date
import json
from typing import Any


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

class CafeRepository:

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
                db.session.rollback()
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
                    db.session.rollback()
                    app.logger.error(f"db_cafe: Failed to delete Cafe for cafe_id = '{cafe_id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Modify
    # -------------------------------------------------------------------------------------------------------------- #
    # Update an existing cafe
    @staticmethod
    def update_cafe(cafe: CafeModel) -> CafeModel | None:
        with app.app_context():
            try:
                db.session.add(cafe)
                db.session.commit()
                db.session.refresh(cafe)
                return cafe

            except Exception as e:
                db.session.rollback()
                app.logger.error(f"dB.update_cafe(): Failed to add update '{cafe.name}', error code was '{e.args}'.")
                return None

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
                    db.session.rollback()
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
                    db.session.rollback()
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
                    db.session.rollback()
                    app.logger.error(f"dB.unclose_cafe(): Failed with cafe '{cafe.name}', error code was '{e.args}'.")
                    return False

        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Search
    # -------------------------------------------------------------------------------------------------------------- #
    # Return a list of all cafes
    @staticmethod
    def all_cafes() -> list[CafeModel]:
        """
        Return all the cafes in the tabel ordered by id.
        :return:            List of cafes.
        """
        with app.app_context():
            cafes = CafeModel.query.order_by('id').all()
            return cafes

    @staticmethod
    def all_cafes_sorted() -> list[CafeModel]:
        """
        Return all the cafes in the tabel ordered by name.
        :return:            List of cafes.
        """
        with app.app_context():
            cafes = CafeModel.query.order_by('name').all()
            return cafes

    # Return a single cafe
    @staticmethod
    def one_by_id(id: int) -> CafeModel | None:
        with app.app_context():
            cafe = CafeModel.query.filter_by(id=id).first()
            # Will return nothing if id is invalid
            return cafe

    @staticmethod
    def one_by_name(name: str) -> CafeModel | None:
        with app.app_context():
            cafe = CafeModel.query.filter_by(name=name).first()
            # Will return nothing if name is invalid
            return cafe

    @staticmethod
    def find_all_cafes_by_email(email: str) -> list[CafeModel]:
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
    @staticmethod
    def cafes_passed_by_gpx(cafes_passed: str) -> list[dict[str, Any]]:
        """
        Convert the cafes_passed JSON string from the GPX database into a list of dictionaries for jinja to use in the gpx_details.html template.
        :param cafes_passed:                This is the string from gpx.cafes_passed which is a JSON string, comprising
                                            a list of dictionaries of the form:
                                            {"cafe_id": int, "dist_km": float, "range_km": float}
        :return:                            Return a sorted list of dictionaries for jinja to use to display cafe details.
                                            The list if sorted by range and the dictionary format is:
                                            'id':           An identifier for the café, typically an integer.
                                            'name':         The name of the café, typically a string.
                                            'lat':          Latitude coordinate of the café, typically a float.
                                            'lon':          Longitude coordinate of the café, typically a float.
                                            'dist_km':      The distance of the café in kilometers, which can be a float or `None` if no data is available.
                                            'range_km':     The range of the café in kilometers, which can be a float or `None` if no data is available.
                                            'status':       The active status of the café, typically a boolean (`True` or `False`).
        """
        # ----------------------------------------------------------- #
        # Validate cafes_passed JSON string
        # ----------------------------------------------------------- #
        try:
            cafes_json: list[dict[str, Any]] = json.loads(cafes_passed)
        except Exception:
            # Failed to parse JSON for some reason
            return []

        if not cafes_json:
            # No cafes
            return []

        # ----------------------------------------------------------- #
        # Get a list of IDs
        # ----------------------------------------------------------- #
        cafe_ids: list[int] = [dct["cafe_id"] for dct in cafes_json]

        # ----------------------------------------------------------- #
        # Get all cafes from those IDs
        # ----------------------------------------------------------- #
        if cafe_ids:
            with app.app_context():
                cafes: list[CafeModel] = CafeModel.query.filter(CafeModel.id.in_(cafe_ids)).all()  # type: ignore

        # ----------------------------------------------------------- #
        # Build our return list of cafe info
        # ----------------------------------------------------------- #
        cafe_list: list[dict[str, Any]] = []
        for cafe in cafes:
            cafe_json: dict[str, Any] | None = next((dct for dct in cafes_json if dct["cafe_id"] == cafe.id), None)
            cafe_summary: dict[str, Any] = {
                'id': cafe.id,
                'name': cafe.name,
                'lat': cafe.lat,
                'lon': cafe.lon,
                'dist_km': cafe_json['dist_km'] if cafe_json else None,
                'range_km': cafe_json['range_km'] if cafe_json else None,
                'status': cafe.active,
            }
            cafe_list.append(cafe_summary)

        # ----------------------------------------------------------- #
        # Sort by range
        # ----------------------------------------------------------- #
        return sorted(cafe_list, key=lambda x: x['range_km'])
