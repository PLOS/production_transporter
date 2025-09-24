from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from janeway_ftp import helpers

import plugins.production_transporter.consts.consts as consts
from core import models as core_models
from journal.models import Journal
from plugins.production_transporter import utils
from submission import models
from utils.logger import get_logger
from utils.setting_handler import get_setting as get_setting_handler

logger = get_logger(__name__)


class Command(BaseCommand):
    help = "Deposits an article on a production FTP server."

    def add_arguments(self, parser):
        parser.add_argument('article_id')
        parser.add_argument('user_id')

    @staticmethod
    def __get_transport_stage(journal: Journal) -> str | None:
        setting_name = consts.PLUGIN_SETTINGS_TRANSPORT_STAGE
        logger.debug(f"Getting setting for {setting_name} in journal {journal.code}")
        try:
            return get_setting_handler(setting_group_name=consts.PLUGIN_SETTINGS_GROUP_NAME,
                                       setting_name=setting_name, journal=journal).process_value()
        except ObjectDoesNotExist as e:
            logger.exception(e)
            logger.error("Could not get the following setting, '{0}'.".format(setting_name))
            return None

    def handle(self, *args, **options):
        article_id = options.get('article_id')
        user_id = options.get('user_id')

        try:

            article = models.Article.objects.get(
                    pk=article_id,
            )
            stage: str = self.__get_transport_stage(article.journal)
            user = core_models.Account.objects.get(pk=user_id)
            kwargs = {
                'article': article,
                'request': helpers.create_fake_request(
                        article.journal,
                        user,
                )
            }
            utils.on_article_stage(
                    stage,
                    kwargs
            )
        except (models.Article.DoesNotExist, core_models.Account.DoesNotExist):
            exit('No article or user found with supplied IDs.')
