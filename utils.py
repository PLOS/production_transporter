from plugins.production_transporter.file_transport.file_transporter import FileTransporter
from plugins.production_transporter.utilities import data_fetch
from plugins.production_transporter.utilities.settings import ProductionTransporterSettings
from submission import models as submission_models
from typing import Tuple, Optional, Dict
from utils.logger import get_logger
from django_tasks import task

logger = get_logger(__name__)


def extract_user_info(request) -> Optional[Dict]:
    """
    Extract minimal user data from the request.
    :param request: Django's HttpRequest

    Returns:
    A dictionary with user id, username, and email if user exists, else None.
    """
    user = getattr(request, "user", None)
    if user:
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name(),
            "is_anonymous": user.is_anonymous,
        }
    return None


def extract_journal_info(request) -> Optional[Dict]:
    """
    Extract minimal journal data from the request.
    :param request: Django's HttpRequest

    Returns:
    A dictionary with journal code if journal exists, else None.
    """
    journal = getattr(request, "journal", None)
    if journal:
        return {"code": journal.code}
    return None


def verify_request_has_required_data(request) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Verify and extract essential request data for serialization.
    :param request: Django's HttpRequest

    Returns:
        Tuple of (user_repr, journal_repr), where each may be None
        if not present or valid.
    """
    try:
        user_repr = extract_user_info(request)
        journal_repr = extract_journal_info(request)
        return user_repr, journal_repr
    except Exception as exception:
        logger.exception(exception)
        logger.error("Failed to extract required user or journal data from request.", )
        return None, None

def extract_filtered_headers(request, allowed_headers=None) -> Dict:
    """
    Extract a subset of headers from a Django request.
    :param request: Django's HttpRequest
    :param allowed_headers: list[str] of allowed header names (case-insensitive)

    Returns:
    A dictionary containing only the allowed headers.
    """
    if allowed_headers is None:
        allowed_headers = ["user-agent", "referer", "accept", "content-type"]

    filtered_headers = {}
    for header_name, header_value in request.headers.items():
        if header_name.lower() in allowed_headers:
            filtered_headers[header_name] = header_value

    return filtered_headers

def serialize_request(request) -> Dict:
    """
    Return a simplified, serializable version of a Django HttpRequest suitable for background tasks.
    :param request: Django's HttpRequest

    Returns:
    A dictionary containing essential request data (useful outside of HTTP context).
    """
    user_repr, journal_repr = verify_request_has_required_data(request)
    site_type = getattr(request, "site_type", None)
    site_type_repr = {"name": site_type.name} if site_type else None

    return {
        "method": request.method,
        "path": request.path,
        "full_path": request.get_full_path(),
        "remote_addr": request.META.get("REMOTE_ADDR"),
        "host": request.get_host(),
        "content_type": request.META.get("CONTENT_TYPE"),
        "query_params": dict(request.GET),
        "post_data": dict(request.POST) if request.method == "POST" else None,
        "user": user_repr,
        "journal": journal_repr,
        "site_type": site_type_repr,
        "headers": extract_filtered_headers(request),
    }

def schedule_file_transfer(request, journal_code: str, article_id: int = None, send_email: bool = True,
                           show_notifications: bool = True, ) -> None:
    """
    Schedules a file transfer by calling the django-task, do_file_transfer.
    Creates a serializable request that can be passed to the task queue.

    :param request: Request (Django's HttpRequest) must contain the article, journal, and user making the request.
    :param journal_code: Journal code where the article is located.
    :param article_id: The ID of the article to transfer.
    :param send_email: True if an email should be sent upon a successful transfer, False otherwise.
    :param show_notifications: True if a pop-up notification should be shown (note that popups will not show if sent using a background task).
    """
    serializable_request = serialize_request(request)
    do_file_transfer.enqueue(serializable_request, journal_code, article_id=article_id, send_email=send_email,
                             show_notifications=show_notifications)

@task()
def do_file_transfer(serializable_request, journal_code: str, article_id: int = None, send_email: bool = True,
                     show_notifications: bool = True, ) -> None:
    """
    Does a file transfer.
    :param serializable_request: Request must contain the article, journal, and user making the request.
    :param journal_code: The journal code where the article is located.
    :param article_id: The ID of the article to transfer.
    :param send_email: True if an email should be sent upon a successful transfer, False otherwise.
    :param show_notifications: True if a pop-up notification should be shown (note that popups will not show if sent using a background task).
    :return:
    """
    journal = data_fetch.fetch_journal_data(journal_code)
    file_transporter: FileTransporter = FileTransporter(request=serializable_request, journal=journal,
                                                        article_id=article_id, send_email=send_email,
                                                        show_notifications=show_notifications)
    file_transporter.collect_and_send_article()


def get_ftp_submission_stage(settings: ProductionTransporterSettings):
    submission_stage = settings.transport_production_stage

    if not submission_stage:
        return submission_models.STAGE_ACCEPTED
    else:
        return submission_stage


def on_article_stage(stage: str, kwargs):
    request = kwargs.get('request')
    settings = data_fetch.fetch_settings(request.journal)
    submission_stage = get_ftp_submission_stage(settings)
    if submission_stage != stage:
        return
    article = kwargs.get('article')
    journal_code = request.journal.code
    schedule_file_transfer(request=request, journal_code=journal_code, article_id=article.id)


def on_article_accepted(**kwargs):
    on_article_stage(submission_models.STAGE_ACCEPTED, kwargs)


def on_article_submitted(**kwargs):
    on_article_stage(submission_models.STAGE_UNASSIGNED, kwargs)


def on_article_published(**kwargs):
    on_article_stage(submission_models.STAGE_PUBLISHED, kwargs)
