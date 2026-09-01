from django.contrib import messages
from django.http import HttpRequest
from journal.models import Journal
from plugins.production_transporter.utilities import logger_messages
from submission.models import Article
from utils.logger import get_logger
from utils.notify_helpers import send_email_with_body_from_user
from utils.render_template import get_requestless_content

logger = get_logger(__name__)


def send_export_success_notification_email(request, journal: Journal, article: Article, production_contact_email: str):
    """Send notification email to production manager"""

    if not production_contact_email:
        message = logger_messages.no_production_contact_set()
        logger.warning(message)
        if isinstance(request, HttpRequest):
            messages.add_message(
                    request,
                    messages.WARNING,
                    message,
            )
        return

    notification_context = {
        'journal': journal,
        'article': article,
    }
    notification_content = get_requestless_content(
            context=notification_context,
            journal=journal,
            template='transport_email_production_manager',
            group_name='plugin',
    )

    send_email_with_body_from_user(
            request=request,
            subject='New Article Deposited',
            to=production_contact_email,
            body=notification_content,
            log_dict={
                'level': 'Info',
                'action_text': 'Article deposited on production FTP server.',
                'types': 'Article Deposited',
                'target': article,
            }
    )
