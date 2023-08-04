from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, current_user, logout_user, login_required
from datetime import date
from werkzeug import exceptions


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

@app.route('/mark_read', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def mark_read():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    message_id = request.args.get('message_id', None)
    return_to = request.args.get('return_to', None)

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

    # Back to calling page
    if return_to:
        return redirect(return_to)
    else:
        return redirect(request.referrer)


# -------------------------------------------------------------------------------------------------------------- #
# Mark message as unread
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/mark_unread', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def mark_unread():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    message_id = request.args.get('message_id', None)
    return_to = request.args.get('return_to', None)

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

    # Back to calling page
    if return_to:
        return redirect(return_to)
    else:
        return redirect(request.referrer)


# -------------------------------------------------------------------------------------------------------------- #
# Delete message
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/delete_message', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def delete_message():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    message_id = request.args.get('message_id', None)

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

    # Back to calling page
    return redirect(request.referrer + "#messages")


# -------------------------------------------------------------------------------------------------------------- #
# Reply message
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/reply_message/<int:message_id>', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def reply_message(message_id):
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    body = request.args.get('body', None)

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

    # Back to calling page
    return redirect(request.referrer.split('#')[0] + "#messages")


# -------------------------------------------------------------------------------------------------------------- #
# Send message to Admin
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/message_admin/<int:user_id>', methods=['GET'])
@logout_barred_user
@login_required
@update_last_seen
def message_admin(user_id):
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    body = request.args.get('admin_message', None)

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
        app.logger.debug(f"message_user(): FAILED to locate user user_id = '{user_id}'.")
        Event().log_event("Message Admin Fail", f"FAILED to locate user user_id = '{user_id}'.")
        return abort(404)

    # ----------------------------------------------------------- #
    # Check author is correct
    # ----------------------------------------------------------- #
    if user_id != current_user.id:
        # Fraudulent attempt!
        app.logger.debug(f"message_user(): User '{current_user.email}' attempted to spoor user '{user.email}'.")
        Event().log_event("Message Admin Fail", f"User '{current_user.email}' attempted to spoor user '{user.email}'.")
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

    if Message().add_message(message):
        # Success!
        app.logger.debug(f"message_admin(): User '{user.email}' has sent message = '{body}'")
        Event().log_event("Message Admin Success", f"Message was sent successfully.")
        flash("Your message has been forwarded to the Admin Team")
    else:
        # Should never get here, but...
        app.logger.debug(f"message_admin(): Message().add_message() failed user.email = '{user.email}'.")
        Event().log_event("Message Admin Fail", f"Message send failed!")
        flash("Sorry, something went wrong")

    # Back to calling page
    return redirect(request.referrer)


# -------------------------------------------------------------------------------------------------------------- #
# Send message to user
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/message_user/<int:user_id>', methods=['GET'])
@logout_barred_user
@login_required
@admin_only
@update_last_seen
def message_user(user_id):
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    body = request.args.get('user_message', None)

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

    if Message().add_message(message):
        app.logger.debug(f"message_user(): Admin has sent message to '{user.name}', body = '{body}'.")
        Event().log_event("Message User Success", f"Message was sent successfully to '{user.email}'.")
        flash(f"Your message has been forwarded to {user.name}")
    else:
        # Should never get here, but...
        app.logger.debug(f"message_user(): Message().add_message() failed, user.email = '{user.email}'.")
        Event().log_event("Message User Fail", f"Message send failed to user.email = '{user.email}'.")
        flash("Sorry, something went wrong")

    # Back to calling page
    return redirect(request.referrer)
