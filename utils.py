import importlib
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

def call_transfer_file_function(article_id, function_path):
    """
    Dynamically imports and calls a function to get the file path to transfer for an article.
    function_path: str, e.g. 'plugins.production_transporter.utils.createFileToTransfer'
    Returns the file path as a string.
    """
    module_name, func_name = function_path.rsplit('.', 1)
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)
    return func(article_id)

def collect_and_send_article(request, article):
    transport_enabled = setting_handler.get_setting(
        'plugin',
        'enable_transport',
        request.journal,
    ).processed_value

    if not transport_enabled:
        messages.add_message(
            request,
            messages.INFO,
            'Production deposit is in your workflow but FTP transport is disabled for this journal.',
        )
        return

    transfer_method = setting_handler.get_setting(
        "plugin",
        "transfer_method_type",
        request.journal,
    ).processed_value

    zip_function_path = setting_handler.get_setting(
        "plugin", "file_transfer_zip_function", request.journal
    ).processed_value

    zip_success_callback_path = setting_handler.get_setting( 
        "plugin", "file_transfer_zip_success_callback", request.journal 
    ).processed_value

    zip_failure_callback_path = setting_handler.get_setting( 
        "plugin", "file_transfer_zip_error_callback", request.journal # standardize name with FAILURE rather than ERROR
    ).processed_value

    go_enabled = setting_handler.get_setting( 
        "plugin", "enable_go_file_sending", request.journal 
    ).processed_value

    go_function_path = setting_handler.get_setting( 
        "plugin", "file_transfer_go_function", request.journal 
    ).processed_value

    go_success_callback_path = setting_handler.get_setting( 
        "plugin", "file_transfer_go_success_callback", request.journal 
    ).processed_value

    go_failure_callback_path = setting_handler.get_setting( 
        "plugin", "file_transfer_go_error_callback", request.journal # standardize name with FAILURE rather than ERROR
    ).processed_value

    file_to_send = None
    folder_string = None

    if transfer_method == "File Transfer Protocol":
        if zip_function_path and zip_success_callback_path and zip_failure_callback_path:
            try:
                file_to_send = call_transfer_file_function(
                    str(article.pk), zip_function_path
                )
                if file_to_send:
                    call_transfer_file_function(
                        str(article.pk), zip_success_callback_path
                    )
                else:    
                    call_transfer_file_function(
                        str(article.pk), zip_failure_callback_path
                    )
            except Exception as e:
                messages.add_message(
                    request,
                    messages.WARNING,
                    f"Custom file transfer for .zip failed: {e}",
                )
        if go_enabled and go_function_path and go_success_callback_path and go_failure_callback_path:
            try:
                file_to_send = call_transfer_file_function(
                    str(article.pk), go_function_path
                )
                if file_to_send:
                    call_transfer_file_function(
                        str(article.pk), go_success_callback_path
                    )
                else:    
                    call_transfer_file_function(
                        str(article.pk), go_failure_callback_path
                    )
            except Exception as e:
                messages.add_message(
                    request,
                    messages.WARNING,
                    f"Custom file transfer for .go.xml failed: {e}",
                )
    else:
        file_to_send, folder_string = prep_zip_folder(request, article)

    # Get FTP details
    ftp_server, ftp_username, ftp_password, ftp_remote_directory = get_ftp_details(
        request.journal,
    )
    if not ftp_server or not ftp_username or not ftp_password:
        messages.add_message(
            request,
            messages.WARNING,
            'Article not sent to production, FTP details not provided.',
        )

    try:
        # FTP the file(s) to remote
        ftp.send_file_via_ftp(
            ftp_server=ftp_server,
            ftp_username=ftp_username,
            ftp_password=ftp_password,
            remote_path=ftp_remote_directory,
            file_path=file_to_send,
        )
    except Exception as e:
        logger.error(e)

    # Notify production email address
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
    production_contact_email = setting_handler.get_setting(
        setting_group_name='plugin',
        setting_name='transport_production_manager',
        journal=request.journal,
    ).processed_value

    if production_contact_email:
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
    else:
        messages.add_message(
            request,
            messages.WARNING,
            'No production contact set in the Production Transporter plugin.',
        )

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



