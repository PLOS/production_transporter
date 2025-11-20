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
            journal_code = article.journal.code
            serilizable_request_content = {
                'user': {'id': user_id},
                'journal': {
                    'code': journal_code
                },
                'method': 'CLI',
            }

            utils.do_file_transfer.enqueue(serializable_request=serilizable_request_content, journal_code=journal_code, article_id=article_id,
                                         send_email=False, show_notifications=False)
        except (models.Article.DoesNotExist, core_models.Account.DoesNotExist):
            exit('No article or user found with supplied IDs.')
