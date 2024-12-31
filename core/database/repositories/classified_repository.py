# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db
from core.database.models.classified_model import ClassifiedModel


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# Don't change these as they are in the db
BUY = "BUY"
SELL = "FS"

STATUS_FOR_SALE = "For sale"
STATUS_UNDER_OFFER = "Under offer"
STATUS_SOLD = "Sold"

STATUSES = [STATUS_FOR_SALE,
            STATUS_UNDER_OFFER,
            STATUS_SOLD]


CATEGORIES = ["Complete bikes",
              "Wheels",
              "Bike parts",
              "Bike tools",
              "Clothing",
              "Accessories",
              "Other"]

# Cap how many photos they can have
MAX_NUM_PHOTOS = 5

DELETE_PHOTO = "Delete"
DEL_IMAGE = ["Keep",
             DELETE_PHOTO]


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Classified Repository Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class ClassifiedRepository(ClassifiedModel):

    # ---------------------------------------------------------------------------------------------------------- #
    # Properties
    # ---------------------------------------------------------------------------------------------------------- #
    def next_photo_index(self):
        if self.image_filenames:
            for filename in [f"class_{self.id}_1.jpg",
                             f"class_{self.id}_2.jpg",
                             f"class_{self.id}_3.jpg",
                             f"class_{self.id}_4.jpg",
                             f"class_{self.id}_5.jpg"]:
                if filename not in self.image_filenames:
                    return filename
            return None

        else:
            # Nothing yet, so
            return f"class_{self.id}_1.jpg"

    # ---------------------------------------------------------------------------------------------------------- #
    # Create
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def add_classified(new_classified: ClassifiedModel) -> ClassifiedModel | None:
        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_classified)
                db.session.commit()
                db.session.refresh(new_classified)
                # Return blog item
                return new_classified

            except Exception as e:
                db.session.rollback()
                app.logger.error(f"db.add_classified(): Failed with error code '{e.args}'.")
                return None

    # ---------------------------------------------------------------------------------------------------------- #
    # Modify
    # ---------------------------------------------------------------------------------------------------------- #

    # ---------------------------------------------------------------------------------------------------------- #
    # Delete
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def delete_classified(classified_id: int) -> bool:
        with app.app_context():
            classified = ClassifiedRepository.query.filter_by(id=classified_id).first()
            if classified:
                try:
                    db.session.delete(classified)
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_delete_classified: Failed to delete for classified_id = '{classified_id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    # ---------------------------------------------------------------------------------------------------------- #
    # Search
    # ---------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def all():
        with app.app_context():
            classifieds = ClassifiedRepository.query.order_by(ClassifiedRepository.id.desc()).all()
            return classifieds

    @staticmethod
    def all_by_email(email: str) -> list[ClassifiedModel]:
        with app.app_context():
            classifieds = ClassifiedRepository.query.filter_by(email=email).all()
            return classifieds

    @staticmethod
    def find_by_id(classified_id: int) -> ClassifiedModel | None:
        with app.app_context():
            classified = ClassifiedRepository.query.filter_by(id=classified_id).first()
            return classified

    @staticmethod
    def number_photos(classified_id: int) -> int | None:
        with app.app_context():
            classified = ClassifiedRepository.query.filter_by(id=classified_id).first()
            if classified:
                filenames = classified.image_filenames.split(',')
                num_photos = 0
                for filename in filenames:
                    if filename != "":
                        num_photos += 1
                return num_photos

            else:
                app.logger.error(f"dB.number_photos(): Called with invalid classified_id = '{classified_id}'.")
                return None
