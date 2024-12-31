from datetime import date
import json
from sqlalchemy import func


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db, GRAVEL_CHOICE
from core.subs_gpx_direction import gpx_direction
from core.database.models.gpx_model import GpxModel
from core.database.models.user_model import UserModel


# -------------------------------------------------------------------------------------------------------------- #
# Constants used for uploading routes
# -------------------------------------------------------------------------------------------------------------- #

GPX_ALLOWED_EXTENSIONS = {'gpx'}
TYPE_GRAVEL = GRAVEL_CHOICE
TYPE_ROAD = "Road"
TYPES = [TYPE_ROAD,
         TYPE_GRAVEL,
         "MTB"]


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define GPX Repository Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class GpxRepository(GpxModel):

    # -------------------------------------------------------------------------------------------------------------- #
    # Create
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def add_gpx(new_gpx: GpxModel) -> GpxModel | None:

        # Update some details
        new_gpx.date = date.today().strftime("%d%m%Y")

        # Try and add to dB
        with app.app_context():
            try:
                db.session.add(new_gpx)
                db.session.commit()
                db.session.refresh(new_gpx)
                return new_gpx
            
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"db_gpx: Failed to add GPX '{new_gpx.name}', "
                                 f"error code '{e.args}'.")
                return None
            
    # -------------------------------------------------------------------------------------------------------------- #
    # Modify
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def update_filename(gpx_id: id, filename: str) -> bool:
        with app.app_context():
            gpx = GpxModel.query.filter_by(id=gpx_id).first()
            if gpx:
                try:
                    # Update filename
                    gpx.filename = filename
                    gpx.direction = gpx_direction(filename, gpx_id)
                    # Write to dB
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_gpx: Failed to update filename for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    @staticmethod
    def update_downloads(gpx_id: int, email: str) -> bool:
        with app.app_context():
            gpx = GpxModel.query.filter_by(id=gpx_id).first()
            if gpx:
                try:
                    # Update filename
                    if gpx.downloads:
                        emails = json.loads(gpx.downloads)
                        if not email in emails:
                            emails.append(email)
                    else:
                        # Start new set
                        emails = [email]
                    # Write to dB
                    gpx.downloads = json.dumps(emails)
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_gpx: Failed to update downloads for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    @staticmethod
    def clear_cafe_list(gpx_id: int) -> bool:
        with app.app_context():
            gpx = GpxModel.query.filter_by(id=gpx_id).first()
            if gpx:
                try:
                    # Note, the cafes_passed is a JSON string, not a list!
                    gpx.cafes_passed = "[]"
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_gpx: Failed to clear cafe list for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    @staticmethod
    def update_cafe_list(gpx_id: int, cafe_id: int, dist_km: float, range_km: float):
        with app.app_context():
            gpx = GpxModel.query.filter_by(id=gpx_id).first()
            if gpx:
                try:
                    # Get the list of cafes passed
                    # eg [  {"cafe_id": 1, "dist_km": 0.1, "range_km": 70},
                    #       {"cafe_id": 2, "dist_km": 0.2, "range_km":30}
                    #    ]
                    cafes_json = json.loads(gpx.cafes_passed)
                    updated = False

                    for cafe in cafes_json:
                        if cafe['cafe_id'] == cafe_id:
                            cafe['dist_km'] = round(dist_km, 1)
                            cafe['range_km'] = round(range_km, 1)
                            updated = True

                    if not updated:
                        # Tag on the end
                        cafes_json.append({
                            "cafe_id":  cafe_id,
                            "dist_km":  round(dist_km, 1),
                            "range_km": round(range_km, 1)
                        })

                    # Push back to gpx
                    gpx.cafes_passed = json.dumps(cafes_json)

                    # Update dB
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_gpx: Failed to update cafe list for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    @staticmethod
    def remove_cafe_list(gpx_id: int, cafe_id: int) -> bool:
        with app.app_context():
            gpx = GpxModel.query.filter_by(id=gpx_id).first()
            if gpx:
                try:
                    # Get the list of cafes passed
                    # eg [  {"cafe_id": 1, "dist_km": 0.1, "range_km": 70},
                    #       {"cafe_id": 2, "dist_km": 0.2, "range_km":30}
                    #    ]
                    cafes_json = json.loads(gpx.cafes_passed)

                    for cafe in cafes_json:
                        if cafe['cafe_id'] == cafe_id:
                            # Need to remove this entry
                            cafes_json.remove(cafe)

                    # Push back to gpx
                    gpx.cafes_passed = json.dumps(cafes_json)

                    # Update dB
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_gpx: Failed to update cafe list for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    @staticmethod
    def update_stats(gpx_id: id, length_km: float, ascent_m: float) -> bool:
        with app.app_context():
            gpx = GpxModel.query.filter_by(id=gpx_id).first()
            if gpx:
                try:
                    # Update route stats
                    gpx.length_km = round(length_km, 1)
                    gpx.ascent_m = round(ascent_m, 1)
                    # Update dB
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_gpx: Failed to update stats for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False

            return False

    @staticmethod
    def publish(gpx_id: id) -> bool:
        with app.app_context():
            gpx = GpxModel.query.filter_by(id=gpx_id).first()
            if gpx:
                try:
                    gpx.public = True
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_gpx: Failed to publish gpx for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    @staticmethod
    def hide(gpx_id: int) -> bool:
        with app.app_context():
            gpx = GpxModel.query.filter_by(id=gpx_id).first()
            if gpx:
                try:
                    gpx.public = False
                    db.session.commit()
                    return True
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_gpx: Failed to hide gpx for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Delete
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def delete_gpx(gpx_id: id) -> bool:
        with app.app_context():
            gpx = GpxModel.query.filter_by(id=gpx_id).first()
            if gpx:
                # Delete the GPX file
                try:
                    db.session.delete(gpx)
                    db.session.commit()
                    return True
                
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_gpx: Failed to delete GPX for gpx_id = '{gpx.id}', "
                                     f"error code '{e.args}'.")
                    return False
                
        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Search
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def all_gpxes() -> list[GpxModel]:
        with app.app_context():
            gpxes = GpxModel.query.all()
            return gpxes

    @staticmethod
    def all_gpxes_sorted_downloads() -> list[GpxModel]:
        with app.app_context():
            gpxes = GpxModel.query.filter_by(valid=1).order_by(func.json_array_length(GpxRepository.downloads).desc()).\
                    limit(10).all()
            return gpxes

    @staticmethod
    def all_gpxes_sorted() -> list[GpxModel]:
        with app.app_context():
            gpxes = GpxModel.query.order_by('name').all()
            return gpxes

    @staticmethod
    def all_gravel() -> list[GpxModel]:
        with app.app_context():
            gpxes = GpxModel.query.filter_by(type=TYPE_GRAVEL).all()
            return gpxes

    @staticmethod
    def all_gpxes_by_email(email: str) -> list[GpxModel]:
        with app.app_context():
            gpxes = GpxModel.query.filter_by(email=email).all()
            return gpxes

    @staticmethod
    def one_by_id(id: int) -> GpxModel | None:
        with app.app_context():
            gpx = GpxModel.query.filter_by(id=id).first()
            return gpx

    # -------------------------------------------------------------------------------------------------------------- #
    # Other
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def gpx_id_from_combo_string(combo_string):
        # Extract id from number in last set of brackets
        gpx_id = combo_string.split('(')[-1].split(')')[0]
        return gpx_id

    # -------------------------------------------------------------------------------------------------------------- #
    # Properties
    # -------------------------------------------------------------------------------------------------------------- #
    def find_all_gpx_for_cafe(self, cafe_id: int, user: UserModel) -> list[GpxModel]:
        # We return a list of GPXes which pass this cafe
        passing_gpx = []
        for gpx in self.all_gpxes():

            # Tortuous logic as current_user won't have '.email' until authenticated....
            if gpx.public:
                can_see = True
            elif not user.is_authenticated:
                can_see = False
            elif user.email == gpx.email:
                can_see = True
            else:
                can_see = False

            if can_see:
                cafes_json = json.loads(gpx.cafes_passed)
                for cafe in cafes_json:
                    if cafe['cafe_id'] == cafe_id:
                        # Alter the GPX object to just have one cafe passed as this is all the
                        # requesting webpage needs to know (it only cares about one cafe)
                        gpx.cafes_passed = cafe
                        passing_gpx.append(gpx)

        return passing_gpx

