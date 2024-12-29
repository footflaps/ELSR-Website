import os


# -------------------------------------------------------------------------------------------------------------- #
# Import db object from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db
from core.database.models.classifieds_model import ClassifiedModel


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes
# -------------------------------------------------------------------------------------------------------------- #


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

# Where we store blog photos
CLASSIFIEDS_PHOTO_FOLDER = os.environ['ELSR_CLASSIFIEDS_PHOTO_FOLDER']

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
# Define Classifieds Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class Classified(ClassifiedModel):

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
    # Functions
    # ---------------------------------------------------------------------------------------------------------- #
    def all(self):
        with app.app_context():
            classifieds = db.session.query(Classified).order_by(Classified.id.desc()).all()
            return classifieds

    def all_by_email(self, email):
        with app.app_context():
            classifieds = db.session.query(Classified).filter_by(email=email).all()
            return classifieds

    def find_by_id(self, classified_id):
        with app.app_context():
            classified = db.session.query(Classified).filter_by(id=classified_id).first()
            return classified

    def number_photos(self, classified_id):
        with app.app_context():
            classified = db.session.query(Classified).filter_by(id=classified_id).first()
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

    def add_classified(self, new_classified):
        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_classified)
                db.session.commit()
                # Return blog item
                return db.session.query(Classified).filter_by(id=new_classified.id).first()
            except Exception as e:
                app.logger.error(f"db.add_classified(): Failed with error code '{e.args}'.")
                return None

    def delete_classified(self, classified_id):
        with app.app_context():
            classified = db.session.query(Classified).filter_by(id=classified_id).first()
            if classified:
                try:
                    db.session.delete(classified)
                    db.session.commit()
                    return True
                except Exception as e:
                    app.logger.error(f"db_delete_classified: Failed to delete for classified_id = '{classified_id}', "
                                     f"error code '{e.args}'.")
                    return False
        return False


# -------------------------------------------------------------------------------------------------------------- #
# Create the actual dB
# -------------------------------------------------------------------------------------------------------------- #

# This seems to be the only one which works?
with app.app_context():
    db.create_all()


# -------------------------------------------------------------------------------------------------------------- #
# Check the dB loaded ok
# -------------------------------------------------------------------------------------------------------------- #

with app.app_context():
    classifieds = db.session.query(Classified).all()
    print(f"Found {len(classifieds)} classifieds in the dB")
    app.logger.debug(f"Start of day: Found {len(classifieds)} classifieds in the dB")



