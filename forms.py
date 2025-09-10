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

    def clean(self):
        cleaned_data = super().clean()
        
        # If password field is empty, remove it from cleaned_data
        # so the existing password in the database is preserved
        if 'transport_ftp_password' in cleaned_data and not cleaned_data['transport_ftp_password']:
            del cleaned_data['transport_ftp_password']
            
        return cleaned_data