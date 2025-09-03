from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages

from janeway_ftp import ftp

from plugins.production_transporter import plugin_settings, utils as pt_utils
from core import forms, files
from submission import models
from utils import setting_handler
from security.decorators import has_journal, any_editor_user_required
from submission import models as submission_models


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
                [submission_models.STAGE_ACCEPTED,'Accepted'],
                [submission_models.STAGE_UNASSIGNED,'Submitted'],
                [submission_models.STAGE_PUBLISHED,'Published']
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
            'name': 'transport_custom_files',
            'object': setting_handler.get_setting('plugin', 'transport_custom_files', request.journal),
            'enables': [
                "transfer_method_type",
                'file_transfer_zip_function',
                'file_transfer_zip_success_callback',
                'file_transfer_zip_failure_callback',
            ],
            'enables_when': True
        },
        {
            'name': 'transfer_method_type',
            'object': setting_handler.get_setting('plugin', 'transfer_method_type', request.journal),
            'choices': [
                ["File Transfer Protocol", "File Transfer Protocol"],
                ["JSON Body", "JSON Body"]],
        },
        {
            'name': 'file_transfer_zip_function',
            'object': setting_handler.get_setting('plugin', 'file_transfer_zip_function', request.journal),
            'required': True
        },
        {
            'name': 'file_transfer_zip_success_callback',
            'object': setting_handler.get_setting('plugin', 'file_transfer_zip_success_callback', request.journal),
            'required': True
        },
        {
            'name': 'file_transfer_zip_failure_callback',
            'object': setting_handler.get_setting('plugin', 'file_transfer_zip_failure_callback', request.journal),
            'required': True
        },
        {
            'name': 'enable_file_transfer_go_xml',
            'object': setting_handler.get_setting('plugin', 'enable_file_transfer_go_xml', request.journal),
            'enables': [
                'file_transfer_go_function',
                'file_transfer_go_success_callback',
                'file_transfer_go_failure_callback',
            ],
            'enables_when': True
        },
        {
            'name': 'file_transfer_go_function',
            'object': setting_handler.get_setting('plugin', 'file_transfer_go_function', request.journal),
            'required': True
        },           
        {
            'name': 'file_transfer_go_success_callback',
            'object': setting_handler.get_setting('plugin', 'file_transfer_go_success_callback', request.journal),
            'required': True
        },
        {
            'name': 'file_transfer_go_failure_callback',
            'object': setting_handler.get_setting('plugin', 'file_transfer_go_failure_callback', request.journal),
            'required': True
        }
    ]

    setting_group = 'plugin'
    manager_form = forms.GeneratedSettingForm(
        settings=settings
    )
    if request.POST:
        manager_form = forms.GeneratedSettingForm(
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
            zipped_folder_path, folder_string = pt_utils.prep_zip_folder(
                request,
                article,
            )
            return files.serve_temp_file(
                zipped_folder_path,
                f"{folder_string}.zip",
            )
        if 'ftp' in request.POST:
            article_pk = request.POST.get('ftp')
            article = get_object_or_404(
                models.Article,
                pk=article_pk,
                journal=request.journal,
            )
            zipped_folder_path, folder_string = pt_utils.prep_zip_folder(
                request,
                article,
            )
            ftp_server, ftp_username, ftp_password, ftp_remote_directory = pt_utils.get_ftp_details(
                request.journal,
            )
            ftp.send_file_via_ftp(
                ftp_server=ftp_server,
                ftp_username=ftp_username,
                ftp_password=ftp_password,
                remote_path=ftp_remote_directory,
                file_path=zipped_folder_path,
            )

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
