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
        Event().log_event("Message Read Fail", f"Missing message_id!")
        print(f"mark_read(): Missing message_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate id
    # ----------------------------------------------------------- #
    message = Message().find_messages_by_id(message_id)
    if not message:
        Event().log_event("Message Read Fail", f"Can't locate message id = '{message_id}'")
        print(f"mark_read(): Can't locate message id = '{message_id}'")
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
        Event().log_event("Message Read Fail", f"Prevented attempt by '{current_user.email}' to mark as "
                                               f"read message id = '{message_id}'")
        print(f"mark_read(): Prevented attempt by '{current_user.email}' to mark as "
              f"read message id = '{message_id}'")
        return abort(403)

    # ----------------------------------------------------------- #
    # Mark as read
    # ----------------------------------------------------------- #
    if Message().mark_as_read(message_id):
        flash("Message has been marked as read")
    else:
        Event().log_event("Message Read Fail", f"Failed to mark as read, id = '{message_id}'")
        print(f"mark_read(): Failed to mark as read, id = '{message_id}'")
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
        Event().log_event("Message unRead Fail", f"Missing message_id!")
        print(f"mark_unread(): Missing message_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate id
    # ----------------------------------------------------------- #
    message = Message().find_messages_by_id(message_id)
    if not message:
        Event().log_event("Message unRead Fail", f"Can't locate message id = '{message_id}'")
        print(f"mark_unread(): Can't locate message id = {message_id}")
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
        Event().log_event("Message Read Fail", f"Prevented attempt by '{current_user.email}' to mark as "
                                               f"unread message id = '{message_id}'")
        print(f"mark_unread(): Prevented attempt by {current_user.email} to mark "
              f"as unread message id = {message_id}")
        return abort(403)

    # ----------------------------------------------------------- #
    # Mark as read
    # ----------------------------------------------------------- #
    if Message().mark_as_unread(message_id):
        flash("Message has been marked as unread")
    else:
        Event().log_event("Message unRead Fail", f"Failed to mark as unread, id = '{message_id}'")
        print(f"mark_unread(): Failed to mark as unread, id = '{message_id}'")
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
        Event().log_event("Message Delete Fail", f"Missing message_id!")
        print(f"delete_message(): Missing user_id!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate id
    # ----------------------------------------------------------- #
    message = Message().find_messages_by_id(message_id)
    if not message:
        Event().log_event("Message Delete Fail", f"Can't locate message id = '{message_id}'")
        print(f"delete_message(): Can't locate message id = {message_id}")
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
        Event().log_event("Message Read Fail", f"Prevented attempt by '{current_user.email}' to Delete "
                                               f"message, id = '{message_id}'")
        print(f"delete_message(): Prevented attempt by {current_user.email} to "
              f"delete message id = {message_id}")
        return abort(403)

    # ----------------------------------------------------------- #
    # Mark as read
    # ----------------------------------------------------------- #
    if Message().delete(message_id):
        flash("Message has been deleted")
    else:
        Event().log_event("Message Delete Fail", f"Failed to delete, id = '{message_id}'")
        print(f"delete_message(): Failed to delete, id = '{message_id}'")
        flash("Sorry, something went wrong")

    # Back to calling page
    return redirect(request.referrer + "#messages")


# -------------------------------------------------------------------------------------------------------------- #
# Reply message
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/reply_message/<int:message_id>', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def reply_message(message_id):
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    body = request.args.get('body', None)

    # Code from when POST used to work!
    # message_id = request.args.get('message_id', None)
    # try:
    #     body = request.form['body']
    # except exceptions.BadRequestKeyError:
    #     body = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not message_id:
        Event().log_event("Message Reply Fail", f"Missing message_id!")
        print(f"reply_message(): Missing message_id!")
        return abort(400)
    elif not body:
        Event().log_event("Message Reply Fail", f"Missing body!")
        print(f"reply_message(): Missing body!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Validate id
    # ----------------------------------------------------------- #
    message = Message().find_messages_by_id(message_id)
    if not message:
        Event().log_event("Message Reply Fail", f"Can't locate message id = '{message_id}'")
        print(f"reply_message(): Can't locate message id = '{message_id}'")
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
        Event().log_event("Message Reply Fail", f"Prevented attempt by '{current_user.email}' to Reply to "
                                                f"message, id = '{message_id}'")
        print(f"reply_message(): Prevented attempt by {current_user.email} to "
              f"reply to message id = {message_id}")
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
        Event().log_event("Message Reply Success", f" User '{current_user.name}' has sent message "
                                                   f"to '{message.from_email}'.")
        print(f"contact_admin(): User {current_user.name} has sent message to {message.from_email}, body = '{body}'")
        flash("Your message has been sent.")
    else:
        Event().log_event("Message Reply Fail", f"Failed to send message.")
        print(f"contact_admin(): Failed to send message from user {current_user.name} with body = '{body}'")
        flash("Sorry, something went wrong")

    # Back to calling page
    return redirect(request.referrer.split('#')[0] + "#messages")


# -------------------------------------------------------------------------------------------------------------- #
# Send message to Admin
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/message_admin', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@update_last_seen
def message_admin():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)

    try:
        body = request.form['message']
    except exceptions.BadRequestKeyError:
        body = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        Event().log_event("Message Admin Fail", f"Missing user_id!")
        print(f"contact_admin(): Missing user_id!")
        return abort(400)
    elif not body:
        Event().log_event("Message Admin Fail", f"Missing body!")
        print(f"contact_admin(): Missing body!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)

    # Check id is valid
    if not user:
        Event().log_event("Message Admin Fail", f"FAILED to locate user user.id = '{user.id}'.")
        print(f"contact_admin(): FAILED to locate user user.id = '{user.id}'")
        return abort(404)

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
        Event().log_event("Message Admin Success", f"Message was sent successfully.")
        print(f"contact_admin(): User {user.name} has sent message = '{body}'")
        flash("Your message has been forwarded to the Admin Team")
    else:
        Event().log_event("Message Admin Fail", f"Message send failed!")
        print(f"contact_admin(): Failed to send message from user {user.name} has sent message = '{body}'")
        flash("Sorry, something went wrong")

    # Back to calling page
    return redirect(request.referrer)


# -------------------------------------------------------------------------------------------------------------- #
# Send message to user
# -------------------------------------------------------------------------------------------------------------- #

@app.route('/message_user', methods=['GET', 'POST'])
@logout_barred_user
@login_required
@admin_only
@update_last_seen
def message_user():
    # ----------------------------------------------------------- #
    # Get details from the page
    # ----------------------------------------------------------- #
    user_id = request.args.get('user_id', None)

    try:
        body = request.form['message']
    except exceptions.BadRequestKeyError:
        body = None

    # ----------------------------------------------------------- #
    # Handle missing parameters
    # ----------------------------------------------------------- #
    if not user_id:
        Event().log_event("Message User Fail", f"Missing user_id!")
        print(f"contact_user(): Missing user_id!")
        return abort(400)
    elif not body:
        Event().log_event("Message User Fail", f"Missing body!")
        print(f"contact_user(): Missing body!")
        return abort(400)

    # ----------------------------------------------------------- #
    # Check params are valid
    # ----------------------------------------------------------- #
    user = User().find_user_from_id(user_id)

    # Check id is valid
    if not user:
        Event().log_event("Message User Fail", f"FAILED to locate user user.id = '{user.id}'")
        print(f"contact_user(): FAILED to locate user user.id = '{user.id}'")
        return abort(404)

    # ----------------------------------------------------------- #
    # Send message to User
    # ----------------------------------------------------------- #

    # Create a new message
    message = Message(
        from_email=user.email,
        to_email=ADMIN_EMAIL,
        body=body
    )

    if Message().add_message(message):
        Event().log_event("Message User Success", f"Message was sent successfully to '{user.email}'.")
        print(f"message_user(): Admin has sent message to '{user.name}', body = '{body}'")
        flash(f"Your message has been forwarded to {user.name}")
    else:
        Event().log_event("Message User Fail", f"Message send failed to '{user.email}'.")
        print(f"message_user(): Failed to send message to '{user.name}', body = '{body}'")
        flash("Sorry, something went wrong")

    # Back to calling page
    return redirect(request.referrer)
