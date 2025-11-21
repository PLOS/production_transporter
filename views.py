import os
from typing import List

from core import files
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, reverse, get_object_or_404
from janeway_ftp import helpers as deposit_helpers
from plugins.production_transporter import plugin_settings, utils as pt_utils
from plugins.production_transporter.file_transport.file_preparer import FilePreparer
from plugins.production_transporter.file_transport.file_transporter import FileTransporter
from plugins.production_transporter.forms import ProductionTransporterSettingsForm
from plugins.production_transporter.utilities import file_utils
from security.decorators import has_journal, any_editor_user_required
from submission import models
from submission import models as submission_models
from utils import setting_handler


@has_journal
@staff_member_required
def index(request):
    settings = [
        {
            'name': 'enable_transport',
            'object': setting_handler.get_setting('plugin', 'enable_transport', request.journal),
        },
        {
            'name': 'transport_production_stage',
            'object': setting_handler.get_setting('plugin', 'transport_production_stage', request.journal),
            'choices': [
                [submission_models.STAGE_ACCEPTED, 'Accepted'],
                [submission_models.STAGE_UNASSIGNED, 'Submitted'],
                [submission_models.STAGE_PUBLISHED, 'Published']
            ]
        },
        {
            'name': 'transport_production_manager',
            'object': setting_handler.get_setting('plugin', 'transport_production_manager', request.journal),
        },
        {
            'name': 'transport_email_production_manager',
            'object': setting_handler.get_setting('plugin', 'transport_email_production_manager', request.journal),
        },
        {
            'name': 'transport_ftp_address',
            'object': setting_handler.get_setting('plugin', 'transport_ftp_address', request.journal),
        },
        {
            'name': 'transport_ftp_username',
            'object': setting_handler.get_setting('plugin', 'transport_ftp_username', request.journal),
        },
        {
            'name': 'transport_ftp_password',
            'object': setting_handler.get_setting('plugin', 'transport_ftp_password', request.journal),
        },
        {
            'name': 'transport_ftp_remote_path',
            'object': setting_handler.get_setting('plugin', 'transport_ftp_remote_path', request.journal),
        },
        {
            'name': 'transfer_method_type',
            'object': setting_handler.get_setting('plugin', 'transfer_method_type', request.journal),
            'choices': [
                ["ftp", "File Transfer Protocol (FTP)"],
                ["sftp", "Secure File Transfer Protocol (SFTP)"]],
        },
        {
            'name': 'enable_transport_custom_zip',
            'object': setting_handler.get_setting('plugin', 'enable_transport_custom_zip', request.journal),
        },
        {
            'name': 'file_transfer_zip_function',
            'object': setting_handler.get_setting('plugin', 'file_transfer_zip_function', request.journal),
        },
        {
            'name': 'file_transfer_zip_success_callback',
            'object': setting_handler.get_setting('plugin', 'file_transfer_zip_success_callback', request.journal),
        },
        {
            'name': 'file_transfer_zip_failure_callback',
            'object': setting_handler.get_setting('plugin', 'file_transfer_zip_failure_callback', request.journal),
        },
        {
            'name': 'enable_transport_custom_go_xml',
            'object': setting_handler.get_setting('plugin', 'enable_transport_custom_go_xml', request.journal),
        },
        {
            'name': 'file_transfer_go_function',
            'object': setting_handler.get_setting('plugin', 'file_transfer_go_function', request.journal),
        },
        {
            'name': 'file_transfer_go_success_callback',
            'object': setting_handler.get_setting('plugin', 'file_transfer_go_success_callback', request.journal),
        },
        {
            'name': 'file_transfer_go_failure_callback',
            'object': setting_handler.get_setting('plugin', 'file_transfer_go_failure_callback', request.journal),
        }
    ]
    setting_group = 'plugin'
    manager_form = ProductionTransporterSettingsForm(
            settings=settings
    )
    if request.POST:
        manager_form = ProductionTransporterSettingsForm(
                request.POST,
                settings=settings,
        )
        if manager_form.is_valid():
            manager_form.save(
                    group=setting_group,
                    journal=request.journal,
            )
            messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Form saved.',
            )
            return redirect(
                    reverse('production_transporter_manager')
            )

    template = 'production_transporter/index.html'
    context = {
        'manager_form': manager_form,
    }
    return render(
            request,
            template,
            context,
    )


@any_editor_user_required
def handshake_url(request):
    articles_in_stage = models.Article.objects.filter(
            stage=plugin_settings.STAGE,
    )
    template = 'production_transporter/handshake.html'

    if request.POST:
        if 'download' in request.POST:

            article_pk = request.POST.get('download')
            article = get_object_or_404(
                    models.Article,
                    pk=article_pk,
                    journal=request.journal,
            )
            file_transporter = FileTransporter(request, request.journal, article)
            file_preparers: List[FilePreparer] = file_transporter.get_files_to_send()
            if not file_preparers or len(file_preparers) <= 0:
                messages.add_message(
                        request,
                        messages.ERROR,
                        'Could not download files.',
                )
                return None

            if len(file_preparers) > 1:
                deposit_folder, zipped_file_name = deposit_helpers.prepare_temp_folder()
                for file_preparer in file_preparers:
                    file_utils.copy_files_to_temp_deposit_folder(file_preparer.get_filepath(), deposit_folder)
                zipped_file_path = deposit_helpers.zip_temp_folder(
                        temp_folder=deposit_folder,
                )
                filename = os.path.basename(zipped_file_path)
            else:
                zipped_file_path = file_preparers[0].get_filepath()
                filename = file_preparers[0].get_filename()

            return files.serve_temp_file(
                    zipped_file_path,
                    f"{filename}.zip",
            )
        if 'ftp' in request.POST:
            article_pk = request.POST.get('ftp')
            article = get_object_or_404(
                    models.Article,
                    pk=article_pk,
                    journal=request.journal,
            )
            pt_utils.schedule_file_transfer(request, journal_code=request.journal.code, article_id=article_pk)

    context = {
        'articles_in_stage': articles_in_stage,
    }
    return render(
            request,
            template,
            context,
    )


@any_editor_user_required
def jump_url(request, article_id):
    return redirect(
            reverse(
                    'manage_archive_article',
                    kwargs={
                        'article_id': article_id,
                    }
            )
    )
