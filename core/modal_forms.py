

# -------------------------------------------------------------------------------------------------------------- #
# Import app from __init__.py
# -------------------------------------------------------------------------------------------------------------- #

from core import app


# -------------------------------------------------------------------------------------------------------------- #
# Delete a comment
# -------------------------------------------------------------------------------------------------------------- #

def delete_comment_modal_form(url, comment_id):
    return f'<div class="modal fade" id="deleteCommentModal{comment_id}" tabindex="-1" role="dialog" aria-labelledby="exampleModalCenterTitle" aria-hidden="true"> ' \
           f'   <div class="modal-dialog modal-dialog-centered" role="document">' \
           f' 		<div class="modal-content">' \
           f' 			<div class="modal-header">' \
           f' 				<h5 class="modal-title" id="exampleModalLongTitle">Delete Comment</h5>' \
           f' 				<button type="button" class="close" data-dismiss="modal" aria-label="Close">' \
           f' 					<span aria-hidden="true">&times;</span>' \
           f' 				</button> 			' \
           f'           </div>' \
           f'		    <div class="modal-body">Do you really want to delete this comment?</div>' \
           f'   		<div class="modal-footer">' \
           f' 				<button type="button" class="btn btn-primary" data-dismiss="modal">Close</button>' \
           f' 				<a href="{url}" type="button" class="btn btn-danger">Delete comment</a> ' \
           f'			</div> 		' \
           f'       </div>' \
           f' 	</div>' \
           f'</div>'


# Add to jinja
app.jinja_env.globals.update(delete_comment_modal_form=delete_comment_modal_form)


# -------------------------------------------------------------------------------------------------------------- #
# Delete a blog post
# -------------------------------------------------------------------------------------------------------------- #

def delete_post_modal_form(url, post_id):
    return f'<div class="modal fade" id="deletePostModal{post_id}" tabindex="-1" role="dialog" aria-labelledby="exampleModalCenterTitle" aria-hidden="true"> ' \
           f'   <div class="modal-dialog modal-dialog-centered" role="document">' \
           f' 		<div class="modal-content">' \
           f' 			<div class="modal-header">' \
           f' 				<h5 class="modal-title" id="exampleModalLongTitle">Delete Post</h5>' \
           f' 				<button type="button" class="close" data-dismiss="modal" aria-label="Close">' \
           f' 					<span aria-hidden="true">&times;</span>' \
           f' 				</button> 			' \
           f'           </div>' \
           f'		    <div class="modal-body">Do you really want to delete this post? <br> NB This cannot be undone.</div>' \
           f'   		<div class="modal-footer">' \
           f' 				<button type="button" class="btn btn-primary" data-dismiss="modal">Close</button>' \
           f' 				<a href="{url}" type="button" class="btn btn-danger" >Delete comment</a> ' \
           f'			</div> 		' \
           f'       </div>' \
           f' 	</div>' \
           f'</div>'


# Add to jinja
app.jinja_env.globals.update(delete_post_modal_form=delete_post_modal_form)


