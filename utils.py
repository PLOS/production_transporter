from journal.models import Journal
from plugins.production_transporter.file_transport.file_transporter import FileTransporter
from plugins.production_transporter.utilities import data_fetch
from plugins.production_transporter.utilities.settings import ProductionTransporterSettings
from submission import models as submission_models
from submission.models import Article
from utils.logger import get_logger

logger = get_logger(__name__)


def do_file_transfer(request, journal: Journal, article_id: int = None, article: Article = None,
                     settings: ProductionTransporterSettings = None, send_email: bool = True,
                     show_notifications: bool = True, ) -> None:
    """
    Does a file transfer.
    :param request: Request must contain the article, journal, and user making the request.
    :param journal: The journal where the article is located.
    :param article_id: The ID of the article to transfer.
    :param article: The article to transfer.
    :param settings: The settings to use.
    :param send_email: True if an email should be sent upon a successful transfer, False otherwise.
    :param show_notifications: True if a pop-up notification should be shown.
    :return:
    """
    file_transporter: FileTransporter = FileTransporter(request, journal, article=article, article_id=article_id,
                                                        settings=settings, send_email=send_email,
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

    do_file_transfer(request, request.journal, article=kwargs.get('article'), settings=settings)


def on_article_accepted(**kwargs):
    on_article_stage(submission_models.STAGE_ACCEPTED, kwargs)


def on_article_submitted(**kwargs):
    on_article_stage(submission_models.STAGE_UNASSIGNED, kwargs)


def on_article_published(**kwargs):
    on_article_stage(submission_models.STAGE_PUBLISHED, kwargs)
