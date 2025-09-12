from pydoc import locate
from typing import Callable, Dict, List, Optional, Tuple
from django.contrib import messages

from janeway_ftp import ftp, helpers as deposit_helpers

from utils.notify_helpers import send_email_with_body_from_user
from utils.render_template import get_requestless_content
from journal.models import Journal
from core import models
from utils.logger import get_logger
from submission import models as submission_models
from plugins.production_transporter.utilities.settings import ProductionTransporterSettings

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
    settings = ProductionTransporterSettings(journal)
    return settings.ftp_server, settings.ftp_username, settings.ftp_password, settings.ftp_remote_directory


def prep_default_zip(request, article: submission_models.Article, is_setting_enabled: bool = False) -> Optional[Tuple[str, str]]:
    if not is_setting_enabled:
        return None

    # Create a temp folder
    temp_deposit_folder, zipped_file_name = deposit_helpers.prepare_temp_folder(
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
    zipped_file_path = deposit_helpers.zip_temp_folder(
        temp_folder=temp_deposit_folder,
    )

    return zipped_file_path, zipped_file_name

def prep_custom_zip(request, article: submission_models.Article, is_setting_enabled: bool = False) -> Optional[Tuple[str, Callable, Callable]]:
    if not is_setting_enabled:
        return None

    settings = ProductionTransporterSettings(request.journal)
    zip_custom_function = settings.custom_zip_settings.custom_function
    zip_success_callback = settings.custom_zip_settings.success_callback
    zip_failure_callback = settings.custom_zip_settings.failure_callback

    #TODO: once settings form has required fields implemented, these checks could be removed
    if not zip_custom_function or not zip_success_callback or not zip_failure_callback:
        return None
    
    zip_file_path = zip_custom_function(request.journal.code, str(article.pk))
    
    
    if not zip_file_path:
        return None
    
    return zip_file_path, zip_success_callback, zip_failure_callback
    
def prep_custom_go_xml(request, article: submission_models.Article, is_setting_enabled: bool = False) -> Optional[Tuple[str, Callable, Callable]]:
    if not is_setting_enabled:
        return None

    settings = ProductionTransporterSettings(request.journal)
    go_custom_function = settings.custom_go_settings.custom_function
    go_success_callback = settings.custom_go_settings.success_callback
    go_failure_callback = settings.custom_go_settings.failure_callback

    #TODO: once settings form has required fields implemented, these checks could be removed
    if not go_custom_function or not go_success_callback or not go_failure_callback:
        return None
    
    go_file_path = go_custom_function(request.journal.code, str(article.pk))
    
    if not go_file_path:
        return None
    
    return go_file_path, go_success_callback, go_failure_callback


def execute_callbacks(journal_code: str, success_callbacks: Dict, failure_callbacks: Dict, transfer_results: Dict) -> None:
    """
    Execute success and failure callback functions after file transfer.
    """

    if transfer_results.get('success'):
        for file_path, callback_data in success_callbacks.items():
            if transfer_results['success'][file_path]:
                success_callback = callback_data['custom_success_callback']
                article_id = callback_data['article_id']
                try:
                    success_callback(journal_code, article_id)
                    logger.debug(f"Success callback executed for {article_id}")
                except Exception as e:
                    logger.error(
                        f"Error executing success callback {article_id} for {file_path}: {e}"
                    )

    if transfer_results.get('failure'):
        for file_path, callback_data in failure_callbacks.items():
            if transfer_results['failure'][file_path]:
                failure_callback = callback_data['custom_failure_callback']
                article_id = callback_data['article_id']
                try:
                    failure_callback(journal_code, article_id)
                    logger.info(f"Failure callback executed for {file_path}: {article_id}")
                except Exception as e:
                    logger.error(
                        f"Error executing failure callback {article_id} for {file_path}: {e}"
                    )



def get_files_to_send(request, article: submission_models.Article) -> Tuple[Dict, Dict, Dict]:
    """
    Get the (custom transfer) file path for ZIP / GO XML files
    Returns a file path which will be used to target the file in the ftp transfer
    """
    settings = ProductionTransporterSettings(request.journal)
    files_to_send = dict()
    success_callbacks = dict()
    failure_callbacks = dict()
    enable_transport = settings.transport_enabled
    enable_transport_custom_zip = settings.custom_zip_settings.is_enabled
    enable_transport_custom_go_xml = settings.custom_go_settings.is_enabled


    # Prepare ZIP file for transfer
    default_zip_results = prep_default_zip(request, article, is_setting_enabled=(enable_transport and not enable_transport_custom_zip))
    if default_zip_results:
        default_zip_path, default_zip_file_name = default_zip_results
        files_to_send[default_zip_file_name] = default_zip_path

    # Prepare custom ZIP file for transfer
    custom_zip_result = prep_custom_zip(request, article, is_setting_enabled=(enable_transport and enable_transport_custom_zip))
    if custom_zip_result is not None:
        custom_zip_path, custom_zip_success_callback, custom_zip_failure_callback = custom_zip_result
        files_to_send[custom_zip_path] = custom_zip_path
        success_callbacks[custom_zip_path] = {'custom_success_callback': custom_zip_success_callback, 'required': False, 'article_id': str(article.pk)}
        failure_callbacks[custom_zip_path] = {'custom_failure_callback': custom_zip_failure_callback, 'required': False, 'article_id': str(article.pk)}

    # Prepare GO XML file for transfer if enabled
    custom_go_xml_result = prep_custom_go_xml(request, article, is_setting_enabled=(enable_transport and enable_transport_custom_zip and enable_transport_custom_go_xml))
    if custom_go_xml_result is not None:
        go_xml_path, custom_go_xml_success_callback, custom_go_xml_failure_callback = custom_go_xml_result
        files_to_send[go_xml_path] = go_xml_path
        success_callbacks[go_xml_path] = {'custom_success_callback': custom_go_xml_success_callback, 'required': False, 'article_id': str(article.pk)}
        failure_callbacks[go_xml_path] = {'custom_failure_callback': custom_go_xml_failure_callback, 'required': False, 'article_id': str(article.pk)}

    return files_to_send, success_callbacks, failure_callbacks


def send_files_via_ftp(request, files_to_send) -> Dict:
    ftp_server, ftp_username, ftp_password, ftp_remote_directory = get_ftp_details(
        request.journal,
    )
    if not ftp_server or not ftp_username or not ftp_password:
        logger.error('Failed to send article to production via FTP: FTP details not provided.')
        messages.add_message(
            request,
            messages.ERROR,
            'Failed to send article to production.',
        )
        return {}

    if not files_to_send:
        logger.error('Failed to send article to production via FTP: No file paths provided. If using custom transfer functions, ensure that the functions are returning a file path.')
        messages.add_message(
            request,
            messages.ERROR,
            'Failed to send article to production.',
        )
        return {}

    transfer_results = {}
    
    for file_path in files_to_send.keys():
        try:
            ftp.send_file_via_ftp(
                ftp_server=ftp_server,
                ftp_username=ftp_username,
                ftp_password=ftp_password,
                remote_directory=ftp_remote_directory,
                file_path=file_path,
            )
            transfer_results.setdefault("success", {})[file_path] = True

        except Exception as e:
            transfer_results.setdefault("failure", {})[file_path] = True
            messages.add_message(
                request,
                messages.ERROR,
                f"Failed to send file via FTP: {str(e)}",
            )

    return transfer_results


def send_notification_email(request, article: submission_models.Article, transfer_results: Dict) -> None:
    """Send notification email to production manager"""
    settings = ProductionTransporterSettings(request.journal)
    production_contact_email = settings.production_contact_email

    if not production_contact_email:
        messages.add_message(
            request,
            messages.WARNING,
            'No production contact set in the Production Transporter plugin.',
        )
        return

    if transfer_results.get('success') is None:
        messages.add_message(
            request,
            messages.ERROR,
            'No articles were sent to production: FTP transfer failed.',
        )
        return

    notification_context = {
        'journal': article.journal,
        'article': article,
    }
    notification_content = get_requestless_content(
        context=notification_context,
        journal=article.journal,
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

def collect_and_send_article(request, article: submission_models.Article) -> None:
    """Main function to collect and send article files"""
    settings = ProductionTransporterSettings(request.journal)
    transport_enabled = settings.transport_enabled

    if not transport_enabled:
        messages.add_message(
            request,
            messages.INFO,
            'Production deposit is in your workflow but FTP transport is disabled for this journal.',
        )
        return

    files_to_send, success_callbacks, failure_callbacks = get_files_to_send(request, article)

    transfer_results = send_files_via_ftp(request, files_to_send)
    send_notification_email(request, article, transfer_results)
    execute_callbacks(request.journal.code, success_callbacks, failure_callbacks, transfer_results)


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

    article = kwargs.get('article')
    collect_and_send_article(request, article)

def on_article_accepted(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_ACCEPTED)

def on_article_submitted(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_UNASSIGNED)

def on_article_published(**kwargs):
    on_article_stage(kwargs, submission_models.STAGE_PUBLISHED)
