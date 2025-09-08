from pydoc import locate
from typing import Callable, Optional, Union
from django.contrib import messages

from janeway_ftp import ftp, helpers as deposit_helpers

from utils import setting_handler, notify_helpers, render_template
from core import models
from utils.logger import get_logger
from submission import models as submission_models

logger = get_logger(__name__)


def copy_article_files(article, temp_deposit_folder):
    files_to_copy = []
    latest_manuscript_file = article.manuscript_files.all().latest(
        'date_uploaded'
    )
    files_to_copy.append(latest_manuscript_file)
    for file in article.data_figure_files.all():
        files_to_copy.append(file)

    for file in files_to_copy:
        try:
            deposit_helpers.copy_file(
                article,
                file,
                temp_deposit_folder,
            )
        except FileNotFoundError:
            pass


def get_ftp_details(journal):
    ftp_server = setting_handler.get_setting(
        'plugin',
        'transport_ftp_address',
        journal,
    ).processed_value
    ftp_username = setting_handler.get_setting(
        'plugin',
        'transport_ftp_username',
        journal,
    ).processed_value
    ftp_password = setting_handler.get_setting(
        'plugin',
        'transport_ftp_password',
        journal,
    ).processed_value
    ftp_remote_directory = setting_handler.get_setting(
        'plugin',
        'transport_ftp_remote_path',
        journal,
    ).processed_value

    return ftp_server, ftp_username, ftp_password, ftp_remote_directory


def prep_zip_folder(request, article):
    # Create a temp folder
    temp_deposit_folder, folder_string = deposit_helpers.prepare_temp_folder(
        request=request,
        article=article,
    )

    # Generate JATS stub
    deposit_helpers.generate_jats_metadata(
        article=article,
        article_folder=temp_deposit_folder,
    )

    # Copy all files into folder
    copy_article_files(
        article=article,
        temp_deposit_folder=temp_deposit_folder,
    )

    # Zip Folder
    zipped_deposit_folder = deposit_helpers.zip_temp_folder(
        temp_folder=temp_deposit_folder,
    )

    return zipped_deposit_folder, folder_string

def call_transfer_file_function(journal_code: str, article_id: str, function_path: str) -> Union[str, None]:
    func: Optional[Callable[[str, str], Union[str, None]]] = locate(function_path) # type: ignore
    if func is None:
        raise ImportError(f"Cannot locate {function_path}")
    return func(journal_code, article_id)

def safe_call_transfer(request, article_id: str, function_path: str, error_prefix=None):
    """Safely call `call_transfer_file_function` and return its result or None."""
    journal_code = request.journal.code
    try:
        return call_transfer_file_function(journal_code, str(article_id), function_path)
    except Exception as e:
        prefix = f"{error_prefix}: " if error_prefix else ""
        messages.add_message(
            request,
            messages.WARNING,
            f"{prefix}{e}",
        )
        return None

def get_setting_value(setting_name: str, journal) -> str:
    """Helper function to get plugin setting processed value"""
    return setting_handler.get_setting('plugin', setting_name, journal).processed_value

def get_custom_transfer_file_path(request, article, transfer_type: str) -> Union[str, None]:
    """
    Get the (custom transfer) file path for ZIP / GO XML files
    Returns a file path which will be used to target the file in the ftp transfer
    """
    # Get the function paths based on transfer type
    if transfer_type == 'zip':
        function_path = get_setting_value('file_transfer_zip_function', request.journal)
        success_callback = get_setting_value('file_transfer_zip_success_callback', request.journal)
        failure_callback = get_setting_value('file_transfer_zip_failure_callback', request.journal)
        error_message_prefix = "Custom file transfer for .zip failed"
    else:  # go_xml
        function_path = get_setting_value('file_transfer_go_function', request.journal)
        success_callback = get_setting_value('file_transfer_go_success_callback', request.journal)
        failure_callback = get_setting_value('file_transfer_go_failure_callback', request.journal)
        error_message_prefix = "Custom file transfer for .go.xml failed"

    # Check if all required settings are configured
    if not (function_path and success_callback and failure_callback):
        return None

    # Try to get the file path from the imported module
    file_path = safe_call_transfer(
        request,
        str(article.pk),
        function_path,
        error_prefix=error_message_prefix
    )

    if file_path: # If a file path was returned, then call the SUCCESS callback
        safe_call_transfer(
            request,
            str(article.pk),
            success_callback,
            error_prefix="Success callback error"
        )
        return file_path
    else:
        # If a file path was not returned (i.e., None), then call the FAILURE callback
        safe_call_transfer(
            request,
            str(article.pk),
            failure_callback,
            error_prefix="Failure callback error"
        )
        return None

def send_files_via_ftp(request, files_to_send):
    ftp_server, ftp_username, ftp_password, ftp_remote_directory = get_ftp_details(request.journal)

    if not ftp_server or not ftp_username or not ftp_password:
        messages.add_message(
            request,
            messages.WARNING,
            'Article not sent to production, FTP details not provided.',
        )

    for file_path in files_to_send:
        try:
            ftp.send_file_via_ftp(
                ftp_server=ftp_server,
                ftp_username=ftp_username,
                ftp_password=ftp_password,
                remote_directory=ftp_remote_directory,
                file_path=file_path,
            )
        except Exception as e:
            logger.error(f"Failed to send file {file_path}: {e}")
            messages.add_message(
                request,
                messages.ERROR,
                f"Failed to send file via FTP: {e}",
            )


def send_notification_email(request, article):
    """Send notification email to production manager"""
    production_contact_email = get_setting_value('transport_production_manager', request.journal)

    if not production_contact_email:
        messages.add_message(
            request,
            messages.WARNING,
            'No production contact set in the Production Transporter plugin.',
        )
        return

    notification_context = {
        'journal': article.journal,
        'article': article,
    }
    notification_content = render_template.get_requestless_content(
        context=notification_context,
        journal=article.journal,
        template='transport_email_production_manager',
        group_name='plugin',
    )

    notify_helpers.send_email_with_body_from_user(
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


def collect_and_send_article(request, article):
    """Main function to collect and send article files"""
    transport_enabled = get_setting_value('enable_transport', request.journal)

    if not transport_enabled:
        messages.add_message(
            request,
            messages.INFO,
            'Production deposit is in your workflow but FTP transport is disabled for this journal.',
        )
        return

    files_to_send = []
    enable_transport_custom_files = get_setting_value('enable_transport_custom_files', request.journal)

    if enable_transport_custom_files:
        # Prepare ZIP file for transfer
        zip_file = get_custom_transfer_file_path(request, article, 'zip')
        if zip_file:
            files_to_send.append(zip_file)

        # Prepare GO XML file for transfer if enabled
        go_xml_enabled = get_setting_value('enable_file_transfer_go_xml', request.journal)
        if go_xml_enabled:
            go_xml_file = get_custom_transfer_file_path(request, article, 'go_xml')
            if go_xml_file:
                files_to_send.append(go_xml_file)
    else:
        # Use default zip folder preparation
        zipped_deposit_folder, folder_string = prep_zip_folder(request, article)
        files_to_send.append(zipped_deposit_folder)

    # Send files via FTP
    send_files_via_ftp(request, files_to_send)

    # Send notification email
    send_notification_email(request, article)


def get_ftp_submission_stage(journal):
    submission_stage = setting_handler.get_setting(
        'plugin',
        'transport_production_stage',
        journal,
    ).processed_value

    if not submission_stage:
        return submission_models.STAGE_ACCEPTED
    else:
        return submission_stage

def on_article_stage(kwargs, stage):
    request = kwargs.get('request')
    submission_stage = get_ftp_submission_stage(request.journal)
    if submission_stage != stage:
        return

    article = kwargs.get('article')
    collect_and_send_article(request, article)

def on_article_accepted(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_ACCEPTED)

def on_article_submitted(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_UNASSIGNED)

def on_article_published(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_PUBLISHED)
