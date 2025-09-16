"""
A file which handles file transportation in a cleaner way.
"""
from typing import Set, Tuple

from django.contrib import messages
from janeway_ftp import ftp
from journal.models import Journal
from plugins.production_transporter.file_transport.file_preparer import FilePreparer, DefaultFilePreparer
from plugins.production_transporter.utilities import email_utils
from plugins.production_transporter.utilities.settings import ProductionTransporterSettings
from submission.models import Article
from utils.logger import get_logger

logger = get_logger(__name__)


class FileTransporter:
    def __init__(self, request, journal: Journal, article: Article):
        self.request = request
        self.journal: Journal = journal
        self.article: Article = article
        self.settings = ProductionTransporterSettings(journal)

    def collect_and_send_article(self) -> None:
        """
        Main function to collect and send article files
        """
        if not self.settings.transport_enabled:
            messages.add_message(
                    self.request,
                    messages.INFO,
                    'Production deposit is in your workflow but FTP transport is disabled for this journal.',
            )
            return

        preparers: Set[FilePreparer] = self.get_files_to_send()

        success, error_message, exception = self.send_files_via_ftp(preparers)
        self.execute_callbacks(preparers, success, error_message, exception)
        if success:
            email_utils.send_export_success_notification_email(self.request, self.journal,
                                                               self.article, self.settings.production_contact_email)

    def get_files_to_send(self) -> Set[FilePreparer] | None:
        """
        Get the (custom transfer) file path for ZIP / GO XML files
        Returns a file path which will be used to target the file in the ftp transfer
        """
        file_preparers: Set[FilePreparer] = set()
        enable_transport = self.settings.transport_enabled

        if not enable_transport:
            return None

        # Prepare ZIP file for transfer
        default_zip_result = self.prep_default_zip()
        if default_zip_result is not None:
            file_preparers.add(default_zip_result)

        # Prepare custom ZIP file for transfer
        custom_zip_result = self.prep_custom_zip()
        if custom_zip_result is not None:
            file_preparers.add(custom_zip_result)

        # Prepare GO XML file for transfer if enabled
        custom_go_xml_result = self.prep_custom_go_xml()
        if custom_go_xml_result is not None:
            file_preparers.add(custom_go_xml_result)

        return file_preparers

    def send_files_via_ftp(self, file_preparers: Set[FilePreparer]) -> Tuple[bool, str | None, Exception | None]:
        """
        Send all the files via FTP transfer
        :param file_preparers: Information on the files to send.
        :return:
        """
        if not self.settings.ftp_server or not self.settings.ftp_username or not self.settings.ftp_password:
            error_message = 'Failed to send article to production via FTP: FTP details not provided.'
            logger.error(error_message)
            messages.add_message(
                    self.request,
                    messages.ERROR,
                    'Failed to send article to production.',
            )
            return False, error_message, None

        if not file_preparers or len(file_preparers) <= 0:
            error_message = 'Failed to send article to production via FTP: No file paths provided. If using custom transfer functions, ensure that the functions are returning a file path.'
            logger.error(error_message)
            messages.add_message(
                    self.request,
                    messages.ERROR,
                    'Failed to send article to production.',
            )
            return False, error_message, None

        for file_preparer in file_preparers:
            success, error_message, exception = self.send_file_via_ftp(file_preparer)
            if not success:
                return False, error_message, exception

        return True, None, None

    def send_file_via_ftp(self, file_preparer: FilePreparer) -> Tuple[bool, str | None, Exception | None]:
        """
        Sends a single file via FTP
        :param file_preparer: Information on the file to send.
        :return: True if the file was successfully sent, False otherwise.
        """
        try:
            file_path: str = file_preparer.get_filepath()
        except Exception as exception:
            error_message = f"Failed to get filepath: {str(exception)}"
            logger.error(error_message)
            messages.add_message(
                    self.request,
                    messages.ERROR,
                    f"Failed to send get the filepath.",
            )
            return False, error_message, exception

        try:
            ftp.send_file_via_ftp(
                    ftp_server=self.settings.ftp_server,
                    ftp_username=self.settings.ftp_username,
                    ftp_password=self.settings.ftp_password,
                    remote_directory=self.settings.ftp_remote_directory,
                    file_path=file_path,
            )

        except Exception as exception:
            error_message = f"Failed to send file via FTP: {str(exception)}"
            logger.error(error_message)
            messages.add_message(
                    self.request,
                    messages.ERROR,
                    f"Failed to send file via FTP.",
            )
            return False, error_message, exception

        return True, None, None

    def prep_default_zip(self) -> FilePreparer | None:
        if not self.settings.transport_enabled or self.settings.enable_transport_custom_files:
            return None

        return DefaultFilePreparer(self.journal, self.article, self.request)

    def prep_custom_zip(self) -> FilePreparer | None:
        if not self.settings.transport_enabled or not self.settings.enable_transport_custom_files:
            return None

        return FilePreparer(self.journal, self.article, self.settings.custom_zip_settings.custom_function,
                            self.settings.custom_zip_settings.success_callback,
                            self.settings.custom_zip_settings.failure_callback)

    def prep_custom_go_xml(self) -> FilePreparer | None:
        if not self.settings.transport_enabled or not self.settings.custom_go_settings.is_enabled:
            return None

        return FilePreparer(self.journal, self.article, self.settings.custom_go_settings.custom_function,
                            self.settings.custom_go_settings.success_callback,
                            self.settings.custom_go_settings.failure_callback)

    def execute_callbacks(self, file_preparers: Set[FilePreparer], success: bool, error_message: str | None,
                          error: Exception | None) -> None:
        """
        Execute success and failure callback functions after file transfer.
        """
        for file_preparer in file_preparers:
            self.__attempt_callback(file_preparer, success, error_message, error)

    def __attempt_callback(self, file_preparer: FilePreparer, success: bool, error_message: str | None,
                           error: Exception | None) -> bool:
        """
        Attempts to execute either the success or failure callback.
        :param file_preparer: The information about a file which was sent.
        :param success: If the file was successfully sent.
        :param error_message: The error message that was found, if there was one.
        :param error: The exception that was found, if there was one.
        :return: True if the callback was successful, False otherwise.
        """
        try:
            if success:
                file_preparer.success()
            else:
                file_preparer.failure(error_message, error)
            logger.debug(
                f"{'Success' if success else 'Failure'} callback executed for export of article (ID: '{self.article.pk}') for filepath (Filepath: '{file_preparer.get_filepath()}').")
        except Exception as e:
            logger.error(
                    f"Error while executing {'success' if success else 'failure'} callback for export of article (ID: '{self.article.pk}') for filepath (Filepath: '{file_preparer.get_filepath()}'): {e}"
            )
            return False
        return True
