from flask import redirect, url_for, flash, request, abort
from flask_login import current_user, login_required
from werkzeug import exceptions
from threading import Thread


# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Import our own Classes
# -------------------------------------------------------------------------------------------------------------- #

from core.db_users import User, admin_only, update_last_seen, logout_barred_user
from core.db_messages import Message, ADMIN_EMAIL
from core.dB_events import Event
from core.subs_email_sms import alert_admin_via_sms, send_message_notification_email


# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# html routes
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------- #
# Mark message as read
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/mark_read', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def mark_read():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    message_id = request.args.get('message_id', None)
    return_path = request.args.get('return_path', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not message_id:
        app.logger.debug(f"mark_read(): Missing message_id!")
        Event().log_event("Message Read Fail", f"Missing message_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate id
    # ----------------------------------------------------------- #
    message = Message().find_messages_by_id(message_id)
    if not message:
        app.logger.debug(f"mark_read(): Can't locate message id = '{message_id}'.")
        Event().log_event("Message Read Fail", f"Can't locate message id = '{message_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Any admin can read an email to Admin (as we have multiple Admins, each with a different email address)
    # 2. Message must have been sent to the current user
    if (message.to_email == ADMIN_EMAIL
        and not current_user.admin()) and \
            message.to_email != current_user.email:
        app.logger.debug(f"mark_read(): Prevented attempt by '{current_user.email}' to mark as "
                         f"read message id = '{message_id}'.")
        Event().log_event("Message Read Fail", f"Prevented attempt by '{current_user.email}' to mark as "
                                               f"read message id = '{message_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Mark as read
    # ----------------------------------------------------------- #
    if Message().mark_as_read(message_id):
        flash("Message has been marked as read")
    else:
        # Should never get here, but...
        app.logger.debug(f"mark_read(): Message().mark_as_read() failed, message id = '{message_id}'.")
        Event().log_event("Message Read Fail", f"Failed to mark as read, id = '{message_id}'.")
        flash("Sorry, something went wrong")

    # ----------------------------------------------------------- #
    # Back to calling page
    # ----------------------------------------------------------- #
    # We could have come from either the Admin page or the User page, both of which should pass us "return_path"
    if return_path and \
            return_path != "None":
        return redirect(return_path)
    else:
        # Should never get here, but default to user page if we didn't get "return_path"
        user_id = current_user.id
        return redirect(url_for("user_page", user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Mark message as unread
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/mark_unread', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def mark_unread():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    message_id = request.args.get('message_id', None)
    return_path = request.args.get('return_path', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not message_id:
        app.logger.debug(f"mark_unread(): Missing message_id!")
        Event().log_event("Message unRead Fail", f"Missing message_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate id
    # ----------------------------------------------------------- #
    message = Message().find_messages_by_id(message_id)
    if not message:
        app.logger.debug(f"mark_unread(): Can't locate message_id = '{message_id}'")
        Event().log_event("Message unRead Fail", f"Can't locate message_id = '{message_id}'")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Any admin can read an email to Admin (as we have multiple Admins, each with a different email address)
    # 2. Message must have been sent to the current user
    if (message.to_email == ADMIN_EMAIL
        and not current_user.admin()) and \
            message.to_email != current_user.email:
        app.logger.debug(f"mark_unread(): Prevented attempt by '{current_user.email}' to mark "
                         f"as unread message id = '{message_id}'.")
        Event().log_event("Message Read Fail", f"Prevented attempt by '{current_user.email}' to mark as "
                                               f"unread message id = '{message_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Mark as read
    # ----------------------------------------------------------- #
    if Message().mark_as_unread(message_id):
        flash("Message has been marked as unread")
    else:
        # Should never get here, but...
        app.logger.debug(f"mark_unread(): Message().mark_as_unread() failed, message_id = '{message_id}'.")
        Event().log_event("Message unRead Fail", f"Message().mark_as_unread() failed, message_id = '{message_id}'")
        flash("Sorry, something went wrong")

    # ----------------------------------------------------------- #
    # Back to calling page
    # ----------------------------------------------------------- #
    # We could have come from either the Admin page or the User page, both of which should pass us "return_path"
    if return_path and \
            return_path != "None":
        # Go back to specific page
        return redirect(return_path)
    else:
        # Should never get here, but default to user page if we didn't get "return_path"
        user_id = current_user.id
        return redirect(url_for("user_page", user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Delete message
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/delete_message', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def delete_message():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    message_id = request.args.get('message_id', None)
    return_path = request.args.get('return_path', None)

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not message_id:
        app.logger.debug(f"delete_message(): Missing message_id")
        Event().log_event("Message Delete Fail", f"Missing message_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate id
    # ----------------------------------------------------------- #
    message = Message().find_messages_by_id(message_id)
    if not message:
        app.logger.debug(f"delete_message(): Can't locate message id = '{message_id}'.")
        Event().log_event("Message Delete Fail", f"Can't locate message id = '{message_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Any admin can read an email to Admin (as we have multiple Admins, each with a different email address)
    # 2. Message must have been sent to the current user
    if (message.to_email == ADMIN_EMAIL
        and not current_user.admin()) and \
            message.to_email != current_user.email:
        app.logger.debug(f"delete_message(): Prevented attempt by '{current_user.email}' to delete "
                         f"message_id = '{message_id}'.")
        Event().log_event("Message Read Fail", f"Prevented attempt by '{current_user.email}' to Delete "
                                               f"message_id = '{message_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Mark as read
    # ----------------------------------------------------------- #
    if Message().delete(message_id):
        app.logger.debug(f"delete_message(): Success for message_id = '{message_id}'.")
        Event().log_event("Message Delete Success", f"message_id = '{message_id}'")
        flash("Message has been deleted")
    else:
        # Should never get here, but...
        app.logger.debug(f"delete_message(): Message().delete() failed for message_id = '{message_id}'.")
        Event().log_event("Message Delete Fail", f"Failed to delete, message_id = '{message_id}'")
        flash("Sorry, something went wrong")

    # ----------------------------------------------------------- #
    # Back to calling page
    # ----------------------------------------------------------- #
    # We could have come from either the Admin page or the User page, both of which should pass us "return_path"
    if return_path and \
            return_path != "None":
        # Go back to specific page
        return redirect(return_path)
    else:
        # Should never get here, but default to user page if we didn't get "return_path"
        user_id = current_user.id
        return redirect(url_for("user_page", user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Reply message
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/reply_message', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def reply_message():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    message_id = request.args.get('message_id', None)
    return_path = request.args.get('return_path', None)
    try:
        body = request.form['body']
    except exceptions.BadRequestKeyError:
        body = None

    # Stop 400 error for blank string as very confusing (it's not missing, it's blank)
    if body == "":
        body = " "

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not message_id:
        app.logger.debug(f"reply_message(): Missing message_id!")
        Event().log_event("Message Reply Fail", f"Missing message_id!")
        return abort(400)
    elif not body:
        app.logger.debug(f"reply_message(): Missing body!")
        Event().log_event("Message Reply Fail", f"Missing body!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate id
    # ----------------------------------------------------------- #
    message = Message().find_messages_by_id(message_id)
    if not message:
        app.logger.debug(f"reply_message(): Can't locate message_id = '{message_id}'.")
        Event().log_event("Message Reply Fail", f"Can't locate message_id = '{message_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Restrict access
    # ----------------------------------------------------------- #
    # Rules:
    # 1. Any admin can read an email to Admin (as we have multiple Admins, each with a different email address)
    # 2. Message must have been sent to the current user
    if (message.to_email == ADMIN_EMAIL
        and not current_user.admin()) and \
            message.to_email != current_user.email:
        app.logger.debug(f"reply_message(): Prevented attempt by '{current_user.email}' to "
                         f"reply to message id = '{message_id}'.")
        Event().log_event("Message Reply Fail", f"Prevented attempt by '{current_user.email}' to Reply to "
                                                f"message, id = '{message_id}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Send the reply itself
    # ----------------------------------------------------------- #
    # Create a new message
    new_message = Message(
        from_email=message.to_email,
        to_email=message.from_email,
        body=body
    )

    # Try and send it
    if Message().add_message(new_message):
        # Success!
        app.logger.debug(f"reply_message(): User '{current_user.email}' has sent message "
                         f"to '{message.from_email}', body = '{body}'.")
        Event().log_event("Message Reply Success", f" User '{current_user.name}' has sent message "
                                                   f"to '{message.from_email}'.")
        flash("Your message has been sent.")
    else:
        # Should never get here, but...
        app.logger.debug(f"reply_message(): Message().add_message() failed for user.id = '{current_user.id}'.")
        Event().log_event("Message Reply Fail", f"Failed to send message.")
        flash("Sorry, something went wrong")

    # ----------------------------------------------------------- #
    # Alert Admin (if recipient)
    # ----------------------------------------------------------- #
    if message.from_email == ADMIN_EMAIL:
        # Threading won't have access to current_user, so need to acquire persistent user to pass on
        user = User().find_user_from_id(current_user.id)
        Thread(target=alert_admin_via_sms, args=(user, f"Reply Message: {body}",)).start()

    # ----------------------------------------------------------- #
    # Back to calling page
    # ----------------------------------------------------------- #
    # We could have come from either the Admin page or the User page, both of which should pass us "return_path"
    if return_path and \
            return_path != "None":
        # Go back to specific page
        return redirect(return_path)
    else:
        # Should never get here, but default to user page if we didn't get "return_path"
        user_id = current_user.id
        return redirect(url_for("user_page", user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Send message to Admin
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/message_admin', methods=['POST'])
@logout_barred_user
@login_required
@update_last_seen
def message_admin():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)
    try:
        body = request.form['admin_message']
    except exceptions.BadRequestKeyError:
        body = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"message_admin(): Missing user_id!")
        Event().log_event("Message Admin Fail", f"Missing user_id!")
        return abort(400)
    elif not body:
        app.logger.debug(f"message_admin(): Missing body")
        Event().log_event("Message Admin Fail", f"Missing body!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)

    # Check id is valid
    if not user:
        app.logger.debug(f"message_admin(): FAILED to locate user user_id = '{user_id}'.")
        Event().log_event("Message Admin Fail", f"FAILED to locate user user_id = '{user_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check author is correct
    # ----------------------------------------------------------- #
    if user.id != current_user.id:
        # Fraudulent attempt!
        print(f"user_id = '{user_id}', current_user.id = '{current_user.id}' ")
        app.logger.debug(f"message_admin(): User '{current_user.email}' attempted to spoof user '{user.email}'.")
        Event().log_event("Message Admin Fail", f"User '{current_user.email}' attempted to spoof user '{user.email}'.")
        return abort(403)

    # ----------------------------------------------------------- #
    # Send message to Admin
    # ----------------------------------------------------------- #

    # Create a new message
    message = Message(
        from_email=user.email,
        to_email=ADMIN_EMAIL,
        body=body
    )
    # Send it
    message = Message().add_message(message)
    # Either get back the message or None
    if message:
        # Success
        Thread(target=send_message_notification_email, args=(message, ADMIN_EMAIL,)).start()
        app.logger.debug(f"message_admin(): User '{user.email}' has sent message = '{body}'")
        Event().log_event("Message Admin Success", f"Message was sent successfully.")
        flash("Your message has been forwarded to the Admin Team")
    else:
        # Should never get here, but...
        app.logger.debug(f"message_admin(): Message().add_message() failed user.email = '{user.email}'.")
        Event().log_event("Message Admin Fail", f"Message send failed!")
        flash("Sorry, something went wrong")

    # ----------------------------------------------------------- #
    # Alert admin via SMS
    # ----------------------------------------------------------- #
    Thread(target=alert_admin_via_sms, args=(user, body,)).start()

    # Back to user page
    return redirect(url_for("user_page", user_id=user_id))


# -------------------------------------------------------------------------------------------------------------- #
# Send message to user
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/message_user', methods=['POST'])
@login_required
@admin_only
@update_last_seen
def message_user():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)
    try:
        body = request.form['user_message']
    except exceptions.BadRequestKeyError:
        body = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        app.logger.debug(f"message_user(): Missing user_id!")
        Event().log_event("Message User Fail", f"Missing user_id!")
        return abort(400)
    elif not body:
        app.logger.debug(f"message_user(): Missing body!")
        Event().log_event("Message User Fail", f"Missing body!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)

    # Check id is valid
    if not user:
        app.logger.debug(f"message_user(): FAILED to locate user user_id = '{user_id}'.")
        Event().log_event("Message User Fail", f"FAILED to locate user user_id = '{user_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Send message to User
    # ----------------------------------------------------------- #

    # Create a new message
    message = Message(
        from_email=ADMIN_EMAIL,
        to_email=user.email,
        body=body
    )
    # Send it
    message = Message().add_message(message)
    # Either get back the message or None
    if message:
        # Success
        Thread(target=send_message_notification_email, args=(message, user,)).start()
        app.logger.debug(f"message_user(): Admin has sent message to '{user.name}', body = '{body}'.")
        Event().log_event("Message User Success", f"Message was sent successfully to '{user.email}'.")
        flash(f"Your message has been forwarded to {user.name}")
    else:
        # Should never get here, but...
        app.logger.debug(f"message_user(): Message().add_message() failed, user.email = '{user.email}'.")
        Event().log_event("Message User Fail", f"Message send failed to user.email = '{user.email}'.")
        flash("Sorry, something went wrong")

    # Back to user page
    return redirect(url_for("user_page", user_id=user_id))
