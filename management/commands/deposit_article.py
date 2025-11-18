from core import models as core_models
from django.core.management.base import BaseCommand
from janeway_ftp import helpers
from plugins.production_transporter import utils
from submission import models
from utils.logger import get_logger

logger = get_logger(__name__)


class Command(BaseCommand):
    help = "Deposits an article on a production FTP server."

    def add_arguments(self, parser):
        parser.add_argument('article_id')
        parser.add_argument('user_id')

    def handle(self, *args, **options):
        article_id = options.get('article_id')
        user_id = options.get('user_id')

        try:

            article = models.Article.objects.get(
                    pk=article_id,
            )
            user = core_models.Account.objects.get(pk=user_id)
            request = helpers.create_fake_request(
                    article.journal,
                    user,
            )
            utils.schedule_file_transfer(request, article.journal, article=article,
                                         send_email=False, show_notifications=False)
        except (models.Article.DoesNotExist, core_models.Account.DoesNotExist):
            exit('No article or user found with supplied IDs.')
