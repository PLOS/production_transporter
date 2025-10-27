"""
A file which handles file transportation in a cleaner way.
"""
from typing import Tuple, List

from django.contrib import messages
from django.core.handlers.wsgi import WSGIRequest
from janeway_ftp import ftp, sftp
from journal.models import Journal
from plugins.production_transporter.file_transport.file_preparer import FilePreparer, DefaultFilePreparer
from plugins.production_transporter.utilities import email_utils, data_fetch
from plugins.production_transporter.utilities.settings import ProductionTransporterSettings
from submission.models import Article
from utils.logger import get_logger

logger = get_logger(__name__)


class FileTransporter:
    def __init__(self, request, journal: Journal = None, article: Article = None, article_id: int = None,
                 settings: ProductionTransporterSettings = None, send_email: bool = True, show_notifications: bool = True):
        """
        Creates a file transporter to send items via FTP or SFTP.
        :param request: The request object.
        :param journal: The journal where the article is located.
        :param article: The article to transfer.
        :param article_id: The ID of the article to transfer.
        :param settings: The settings for the Production Transporter.
        :param send_email: True if an email should be sent upon success, False otherwise.
        :param show_notifications: True if a pop-up message should be shown to indicate success or failure.
        """
        self.request = request
        self.journal: Journal = journal
        self.send_email: bool = send_email
        self.show_notifications: bool = show_notifications

        if article is None:
            if article_id is None:
                raise Exception("Must provide article or article id")
            if not journal:
                raise Exception("Must provide journal")
            article = data_fetch.fetch_article(journal, article_id)
            if not article:
                raise Exception("Could not find article with id {0}".format(article_id))

        self.article: Article = article
        if settings is None:
            self.settings = data_fetch.fetch_settings(journal)
        else:
            self.settings = settings

    def collect_and_send_article(self) -> bool:
        """
        Main function to collect and send article files
        """
        if not self.settings.transport_enabled and isinstance(self.request, WSGIRequest):
            logger.debug("Transport disabled")
            if self.show_notifications:
                messages.add_message(
                        self.request,
                        messages.INFO,
                        'Production deposit is in your workflow but FTP transport is disabled for this journal.',
                )
            return False

        preparers: List[FilePreparer] = self.get_files_to_send()

        if not preparers or len(preparers) <= 0:
            error_message = 'Failed to send article to production via FTP: No file paths provided. If using custom transfer functions, ensure that the functions are returning a file path.'
            logger.error(error_message)
            if self.show_notifications and isinstance(self.request, WSGIRequest):
                messages.add_message(
                        self.request,
                        messages.ERROR,
                        'Failed to send article to production.',
                )
            return False

        success, error_message, exception = self.send_files(preparers)
        self.execute_callbacks(preparers, success, error_message, exception)
        if success and self.send_email:
            email_utils.send_export_success_notification_email(self.request, self.journal,
                                                               self.article, self.settings.production_contact_email)
        return success

    def get_files_to_send(self) -> List[FilePreparer] | None:
        """
        Get the (custom transfer) file path for ZIP / GO XML files
        Returns a file path which will be used to target the file in the ftp transfer
        """
        file_preparers: List[FilePreparer] = list()
        enable_transport = self.settings.transport_enabled

        if not enable_transport:
            return None

        # Prepare ZIP file for transfer
        default_zip_result = self.prep_default_zip()
        if default_zip_result is not None:
            file_preparers.append(default_zip_result)

        # Prepare custom ZIP file for transfer
        custom_zip_result = self.prep_custom_zip()
        if custom_zip_result is not None:
            file_preparers.append(custom_zip_result)

        # Prepare GO XML file for transfer if enabled
        custom_go_xml_result = self.prep_custom_go_xml()
        if custom_go_xml_result is not None:
            file_preparers.append(custom_go_xml_result)

        return file_preparers

    def send_files(self, file_preparers: List[FilePreparer]) -> Tuple[bool, str | None, Exception | None]:
        """
        Send all the files via FTP transfer
        :param file_preparers: Information on the files to send.
        :return:
        """
        if not self.settings.ftp_server or not self.settings.ftp_username or not self.settings.ftp_password:
            error_message = 'Failed to send article to production via FTP: FTP details not provided.'
            logger.error(error_message)
            if self.show_notifications and isinstance(self.request, WSGIRequest):
                messages.add_message(
                        self.request,
                        messages.ERROR,
                        'Failed to send article to production.',
                )
            return False, error_message, None

        for file_preparer in file_preparers:
            success, error_message, exception = self.send_file(file_preparer)
            if not success:
                return False, error_message, exception

        return True, None, None

    def send_file(self, file_preparer: FilePreparer) -> Tuple[bool, str | None, Exception | None]:
        """
        Sends a single file
        :param file_preparer: Information on the file to send.
        :return: True if the file was successfully sent, False otherwise.
        """
        try:
            file_path: str = file_preparer.get_filepath()
        except Exception as exception:
            error_message = f"Failed to get filepath for article (ID: {self.article.pk})."
            logger.exception(exception)
            logger.error(error_message)
            if self.show_notifications and isinstance(self.request, WSGIRequest):
                messages.add_message(
                        self.request,
                        messages.ERROR,
                        f"Failed to get the filepath.",
                )
            return False, error_message, exception

        ftp_type: str = "FTP"
        try:
            if self.settings.transfer_method_type == "sftp":
                ftp_type = "SFTP"
                self.send_via_sftp(file_path, file_preparer.filename)
            else:
                self.send_via_ftp(file_path)

        except Exception as exception:
            error_message = f"Failed to send file via {ftp_type} for the file '{file_path}'."
            logger.exception(exception)
            logger.error(error_message)
            if self.show_notifications and isinstance(self.request, WSGIRequest):
                messages.add_message(
                        self.request,
                        messages.ERROR,
                        f"Failed to send file via {ftp_type}.",
                )
            return False, error_message, exception

        return True, None, None

    def send_via_ftp(self, file_path: str) -> None:
        """
        Sends the given file via FTP.
        :param file_path: The path to the file to send.
        """
        ftp.send_file_via_ftp(
                ftp_server=self.settings.ftp_server,
                ftp_username=self.settings.ftp_username,
                ftp_password=self.settings.ftp_password,
                remote_directory=self.settings.ftp_remote_directory,
                file_path=file_path,
        )

    def send_via_sftp(self, file_path: str, file_name: str) -> None:
        """
        Sends the given file via SFTP.
        :param file_name: The name of the file to send.
        :param file_path: The path to the file to send.
        """
        sftp.send_file_via_sftp(
                ftp_server=self.settings.ftp_server,
                ftp_username=self.settings.ftp_username,
                ftp_password=self.settings.ftp_password,
                remote_file_path=self.settings.ftp_remote_directory,
                file_path=file_path,
                file_name=file_name,
                confirm_file_sent=False,
        )

    def prep_default_zip(self) -> FilePreparer | None:
        if not self.settings.transport_enabled or self.settings.enable_transport_custom_files:
            return None

        return DefaultFilePreparer(self.journal, self.article, self.request)

    def prep_custom_zip(self) -> FilePreparer | None:
        if not self.settings.transport_enabled or not self.settings.enable_transport_custom_files:
            return None

        return FilePreparer(self.journal, self.article, self.request, self.settings.custom_zip_settings.custom_function,
                            self.settings.custom_zip_settings.success_callback,
                            self.settings.custom_zip_settings.failure_callback)

    def prep_custom_go_xml(self) -> FilePreparer | None:
        if not self.settings.transport_enabled or not self.settings.custom_go_settings.is_enabled:
            return None

        return FilePreparer(self.journal, self.article, self.request, self.settings.custom_go_settings.custom_function,
                            self.settings.custom_go_settings.success_callback,
                            self.settings.custom_go_settings.failure_callback)

    def execute_callbacks(self, file_preparers: List[FilePreparer], success: bool, error_message: str | None,
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
                    f"{'Success' if success else 'Failure'} callback executed for export of article (ID: '{self.article.pk}').")
        except Exception as e:
            logger.exception(e)
            logger.error(
                    f"Error while executing {'success' if success else 'failure'} callback for export of article (ID: '{self.article.pk}')."
            )
            return False
        return True
