"""Definitions of Celery tasks in Askbot
in this module there are two types of functions:

* those wrapped with a @task decorator and a ``_celery_task`` suffix - celery tasks
* those with the same base name, but without the decorator and the name suffix
  the actual work units run by the task

Celery tasks are special functions in a way that they require all the parameters
be serializable - so instead of ORM objects we pass object id's and
instead of query sets - lists of ORM object id's.

That is the reason for having two types of methods here:

* the base methods (those without the decorator and the
  ``_celery_task`` in the end of the name
  are work units that are called from the celery tasks.
* celery tasks - shells that reconstitute the necessary ORM
  objects and call the base methods
"""
import logging
import time
from django.contrib.contenttypes.models import ContentType
from celery.decorators import task
from askbot.models import Activity
from askbot.models import User
from askbot.models import send_instant_notifications_about_activity_in_post
def get_subs_email(user_list):
     users = " (%d):" % len(user_list)
     cnt = len(users)
     pad = " " * cnt
     emails = []
     for user in user_list:
        emails.append(user.email.split('@')[0].lower())
     emails.sort()
     for ustr in emails:
         if(cnt + len(ustr) > 75):
            users +="\n" + pad 
            cnt = len(pad)
         users += " %s" % ustr
         cnt += len(ustr) + 1

     return users 


@task(ignore_results = True)
def record_post_update_celery_task(
        post_id,
        post_content_type_id,
        newly_mentioned_user_id_list = None, 
        updated_by_id = None,
        timestamp = None,
        created = False,
    ):
    #reconstitute objects from the database
    updated_by = User.objects.get(id = updated_by_id)
    post_content_type = ContentType.objects.get(id = post_content_type_id)
    post = post_content_type.get_object_for_this_type(id = post_id)
    newly_mentioned_users = User.objects.filter(
                                id__in = newly_mentioned_user_id_list
                            )


    record_post_update(
        post = post,
        updated_by = updated_by,
        newly_mentioned_users = newly_mentioned_users,
        timestamp = timestamp,
        created = created,
    )

def record_post_update(
        post = None,
        updated_by = None,
        newly_mentioned_users = None,
        timestamp = None,
        created = False
    ):
    """Called when a post is updated. Arguments:

    * ``newly_mentioned_users`` - users who are mentioned in the
      post for the first time
    * ``created`` - a boolean. True when ``post`` has just been created
    * remaining arguments are self - explanatory

    The method does two things:

    * records "red envelope" recipients of the post
    * sends email alerts to all subscribers to the post
    """
    start_time = time.time()

    #todo: take into account created == True case
    (activity_type, update_object) = post.get_updated_activity_data(created)

    update_activity = Activity(
                    user = updated_by,
                    active_at = timestamp, 
                    content_object = post, 
                    activity_type = activity_type,
                    question = post.get_origin_post()
                )
    update_activity.save()

    #what users are included depends on the post type
    #for example for question - all Q&A contributors
    #are included, for comments only authors of comments and parent 
    #post are included
    recipients = post.get_response_receivers(
                                exclude_list = [updated_by, ]
                            )

    update_activity.add_recipients(recipients)

    assert(updated_by not in recipients)

    for user in set(recipients) | set(newly_mentioned_users):
        user.increment_response_count()
        user.save()

    #todo: weird thing is that only comments need the recipients
    #todo: debug these calls and then uncomment in the repo
    #argument to this call
    pre_notif_time = time.time()
    notification_subscribers = post.get_instant_notification_subscribers(
                                    potential_subscribers = recipients,
                                    mentioned_users = newly_mentioned_users,
                                    exclude_list = [updated_by, ]
                                )
    #todo: fix this temporary spam protection plug
    if False:
        if not (updated_by.is_administrator() or updated_by.is_moderator()):
            if updated_by.reputation < 15:
                notification_subscribers = \
                    [u for u in notification_subscribers if u.is_administrator()]

    #Updater always gets an email
    notification_subscribers.append(updated_by)

    pre_email_time = time.time()
    send_instant_notifications_about_activity_in_post(
                            update_activity = update_activity,
                            post = post,
                            recipients = notification_subscribers,
                        )
    debug_str = "\nEmailed%s\n" % get_subs_email(notification_subscribers)
    debug_str += "  Pre-notif Time: %8.3f\n" % float(pre_notif_time - start_time)
    debug_str += "  Sub Search Time: %8.3f\n" % float(pre_email_time - pre_notif_time)
    debug_str += "  Email Time: %8.3f\n" % float(time.time() - pre_email_time)
    debug_str += "Total Elapsed Time: %8.3f" % float(time.time() - start_time)
    logging.critical(debug_str)
