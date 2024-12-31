from datetime import datetime


# -------------------------------------------------------------------------------------------------------------- #
# Import our own classes etc
# -------------------------------------------------------------------------------------------------------------- #

from core import app, db
from core.database.models.social_model import SocialModel


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

# These are in the form and can change
SOCIAL_FORM_PRIVATE = "Private (Regular riders only)"
SOCIAL_FORM_PUBLIC = "Public (Anyone on the internet)"
# Don't change these as they are in the db
SOCIAL_DB_PRIVATE = "PRIVATE"
SOCIAL_DB_PUBLIC = "PUBLIC"
SIGN_UP_YES = "Absolutely"
SIGN_UP_NO = "I just don't care"
SIGN_UP_CHOICES = [SIGN_UP_NO, SIGN_UP_YES]


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# Define Social Repository Class
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

class SocialRepository(SocialModel):

    # -------------------------------------------------------------------------------------------------------------- #
    # Create
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def add_social(new_social: SocialModel) -> SocialModel | None:
        # Try and add to the dB
        with app.app_context():
            try:
                db.session.add(new_social)
                db.session.commit()
                db.session.refresh(new_social)
                return new_social

            except Exception as e:
                db.session.rollback()
                app.logger.error(f"dB.add_social(): Failed with error code '{e.args}'.")
                return None

    # -------------------------------------------------------------------------------------------------------------- #
    # Update
    # -------------------------------------------------------------------------------------------------------------- #

    # -------------------------------------------------------------------------------------------------------------- #
    # Delete
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def delete_social(social_id: int) -> bool:
        with app.app_context():

            # Locate the GPX file
            social = SocialModel.query.filter_by(id=social_id).first()

            if social:
                # Delete the GPX file
                try:
                    db.session.delete(social)
                    db.session.commit()
                    return True

                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"db_social: Failed to delete Social for social_id = '{social_id}', "
                                     f"error code '{e.args}'.")
                    return False

        return False

    # -------------------------------------------------------------------------------------------------------------- #
    # Search
    # -------------------------------------------------------------------------------------------------------------- #
    @staticmethod
    def all() -> list[SocialModel]:
        with app.app_context():
            socials = SocialModel.query.all()
            return socials

    @staticmethod
    def all_by_email(email: str) -> list[SocialModel]:
        with app.app_context():
            socials = SocialModel.query.filter_by(email=email).all()
            return socials

    @staticmethod
    def one_social_id(social_id: id) -> SocialModel | None:
        with app.app_context():
            social = SocialModel.query.filter_by(id=social_id).first()
            return social

    @staticmethod
    def all_socials_date(date_str: str) -> list[SocialModel]:
        with app.app_context():
            socials = SocialModel.query.filter_by(date=date_str).all()
            for social in socials:
                date_str = social.date
                social_date = datetime(int(date_str[4:8]), int(date_str[2:4]), int(date_str[0:2]), 0, 00).date()
                social.long_date = social_date.strftime("%A %b %d %Y")
            return socials

    @staticmethod
    def all_by_date_range(start_date: str, end_date: str) -> list[SocialModel] | None:
        """
        Retrieve all social entries that fall between two dates based on the converted_date column.
        :param start_date:                  Start date in the format 'YYYY-MM-DD'.
        :param end_date:                    End date in the format 'YYYY-MM-DD'.
        :return:                            List of rides between the specified dates.
        """
        with app.app_context():
            try:
                rides = SocialModel.query.filter(SocialModel.converted_date.between(start_date, end_date)).all()
                return rides

            except Exception as e:
                app.logger.error(f"db_social: Failed to filter rides by date range, "
                                 f"error code '{e.args}'.")
                return None

    @staticmethod
    def all_socials_future() -> list[SocialModel]:
        socials = []
        today = datetime.today().date()
        all_socials = SocialModel.query.all()
        for social in all_socials:
            date_str = social.date
            social_date = datetime(int(date_str[4:8]), int(date_str[2:4]), int(date_str[0:2]), 0, 00).date()
            # Either today or in the future
            if social_date >= today:
                social.long_date = social_date.strftime("%A %b %d %Y")
                socials.append(social)
        return socials

