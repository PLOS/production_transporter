from django import forms
from core import forms as core_forms


class ProductionTransporterSettingsForm(core_forms.GeneratedSettingForm):
    def __init__(self, *args, **kwargs):
        super(ProductionTransporterSettingsForm, self).__init__(*args, **kwargs)
        self.fields['transport_ftp_password'].widget = forms.PasswordInput(
            attrs={
                'class': 'password-field',
            }
        )