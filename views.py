from django.shortcuts import render, redirect, reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages

from plugins.production_transporter import plugin_settings
from core import forms
from submission import models
from utils import setting_handler
from security.decorators import has_journal, any_editor_user_required


@has_journal
@staff_member_required
def index(request):
    settings = [
        {
            'name': 'enable_transport',
            'object': setting_handler.get_setting('plugin', 'enable_transport', request.journal),
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
