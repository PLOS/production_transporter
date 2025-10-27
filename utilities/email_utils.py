from django.contrib import messages
from django.core.handlers.wsgi import WSGIRequest
from journal.models import Journal
from submission.models import Article
from utils.notify_helpers import send_email_with_body_from_user
from utils.render_template import get_requestless_content


def send_export_success_notification_email(request, journal: Journal, article: Article, production_contact_email: str):
    """Send notification email to production manager"""

    if not production_contact_email and isinstance(request, WSGIRequest):
        messages.add_message(
                request,
                messages.WARNING,
                'No production contact set in the Production Transporter plugin.',
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
