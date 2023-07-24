import smtplib
import os


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #

admin_email = os.environ['ELSR_ADMIN_EMAIL']
admin_password = os.environ['ELSR_ADMIN_EMAIL_PASSWORD']
my_email = os.environ['ELSR_CONTACT_EMAIL']


VERIFICATION_BODY = "Dear [USER], \n\n" \
                    "This is a verification email from www.elsr.co.uk. \n\n" \
                    "Your verification code is [CODE]. \n" \
                    "It will expire in 24 hours.\n\n" \
                    "To verify your email address, either:\n\n" \
                    "     1. Goto https://www.elsr.co.uk/validate_email and enter your code manually, or \n\n" \
                    "     2. Click on: https://www.elsr.co.uk/validate_email?code=[CODE]&email='[EMAIL]' \n\n" \
                    "If you were not expecting this email and have not visited www.elsr.co.uk, then don't worry, " \
                    "somebody probably made a typo when entering their email address and accidentally entered this " \
                    "one. Just delete this email and forget about it. Without access to this email account they can't " \
                    "continue and will eventually figure out they miss-typed their email address.\n\n" \
                    "Thanks, \n\n" \
                    "The Admin Team\n\n" \
                    "NB: Please do not reply to this email, the account is not monitored."


RESET_BODY = "Dear [USER], \n\n" \
             "This is a password rest email from www.elsr.co.uk. \n\n" \
             "Your reset code is [CODE]. \n" \
             "It will expire in 24 hours.\n\n" \
             "To reset your password, either:\n\n" \
             "     1. Goto https://www.elsr.co.uk/reset and enter your code manually, or \n\n" \
             "     2. Click on: https://www.elsr.co.uk/reset?code=[CODE]&email='[EMAIL]' \n\n" \
             "If you were not expecting this email and have not visited www.elsr.co.uk, then don't worry, " \
             "somebody probably made a typo when entering their email address and accidentally entered this " \
             "one. Just delete this email and forget about it. Without access to this email account they can't " \
             "continue and will eventually figure out they miss-typed their email address.\n\n" \
             "Thanks, \n\n" \
             "The Admin Team\n\n" \
             "NB: Please do not reply to this email, the account is not monitored."


# -------------------------------------------------------------------------------------------------------------- #
# Functions
# -------------------------------------------------------------------------------------------------------------- #

# Send an email
class Email():

    def send_verfication_email(self, target_email, user_name, code):
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
            connection.login(user=admin_email, password=admin_password)
            subject = "Verification email."
            body = VERIFICATION_BODY.replace("[USER]", user_name)
            body = body.replace("[CODE]", str(code))
            body = body.replace("[EMAIL]", target_email)
            try:
                connection.sendmail(
                    from_addr=admin_email,
                    to_addrs=target_email,
                    msg=f"To:{target_email}\nSubject:{subject}\n\n{body}"
                )
                print(f"Email(): sent verification email to {target_email}")
                return True
            except Exception as e:
                print(f"Email(): Failed to send verification email to {target_email}, error code was {e.args}.")
                return False

    def send_reset_email(self, target_email, user_name, code):
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
            connection.login(user=admin_email, password=admin_password)
            subject = "Password reset email."
            body = RESET_BODY.replace("[USER]", user_name)
            body = body.replace("[CODE]", str(code))
            body = body.replace("[EMAIL]", target_email)
            try:
                connection.sendmail(
                    from_addr=admin_email,
                    to_addrs=target_email,
                    msg=f"To:{target_email}\nSubject:{subject}\n\n{body}"
                )
                print(f"Email(): sent reset email to {target_email}")
                return True
            except Exception as e:
                print(f"Email(): Failed to send reset email to {target_email}, error code was {e.args}.")
                return False

    def contact_form_email(self, from_name, from_email, body):
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as connection:
            connection.login(user=admin_email, password=admin_password)
            subject = f"Message from elsr.co.uk from '{from_name}' ({from_email})"
            try:
                connection.sendmail(
                    from_addr=admin_email,
                    to_addrs=my_email,
                    msg=f"To:{my_email}\nSubject:{subject}\n\n{body}"
                )
                print(f"Email(): sent message to me")
                return True
            except Exception as e:
                print(f"Email(): Failed to send message to myself, error code was {e.args}.")
                return False
