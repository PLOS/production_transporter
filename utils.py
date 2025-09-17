from plugins.production_transporter.file_transport.file_transporter import FileTransporter
from plugins.production_transporter.utilities.settings import ProductionTransporterSettings
from submission import models as submission_models
from utils.logger import get_logger

logger = get_logger(__name__)


def get_ftp_submission_stage(settings: ProductionTransporterSettings):
    submission_stage = settings.transport_production_stage

    if not submission_stage:
        return submission_models.STAGE_ACCEPTED
    else:
        return submission_stage


def on_article_stage(kwargs, stage):
    request = kwargs.get('request')
    settings = ProductionTransporterSettings(request.journal)
    submission_stage = get_ftp_submission_stage(settings)
    if submission_stage != stage:
        return

    file_transporter: FileTransporter = FileTransporter(request, request.journal, kwargs.get('article'), settings)
    file_transporter.collect_and_send_article()


def on_article_accepted(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_ACCEPTED)


def on_article_submitted(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_UNASSIGNED)


def on_article_published(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_PUBLISHED)
