from plugins.production_transporter.file_transport.file_transporter import FileTransporter
from plugins.production_transporter.utilities.settings import ProductionTransporterSettings
from submission import models as submission_models
from utils.logger import get_logger

logger = get_logger(__name__)


def get_ftp_submission_stage(journal):
    settings = ProductionTransporterSettings(journal)
    submission_stage = settings.transport_production_stage

    if not submission_stage:
        return submission_models.STAGE_ACCEPTED
    else:
        return submission_stage


def on_article_stage(kwargs, stage):
    request = kwargs.get('request')
    submission_stage = get_ftp_submission_stage(request.journal)
    if submission_stage != stage:
        return

    file_transporter: FileTransporter = FileTransporter(request, kwargs.get('journal'), kwargs.get('article'))
    file_transporter.collect_and_send_article()


def on_article_accepted(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_ACCEPTED)


def on_article_submitted(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_UNASSIGNED)


def on_article_published(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_PUBLISHED)
