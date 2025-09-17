"""
This adds a class to handle the functionality of preparing files and any actions taken upon success or failure.
"""
import os
from typing import Callable

from janeway_ftp import helpers as deposit_helpers

from journal.models import Journal
from plugins.production_transporter.utilities import file_utils
from submission.models import Article
from utils.logger import get_logger

logger = get_logger(__name__)


class FilePreparer():
    def __init__(self, journal: Journal, article: Article, request, filepath_fetcher: Callable | None = None,
                 success_callback: Callable | None = None, failure_callback: Callable | None = None):
        self.request = request
        self.journal = journal
        self.article = article
        self.journal_code = journal.code
        self.article_id = article.pk
        self.filepath: str | None = None
        self.file_folder: str | None = None
        self.filename: str | None = None
        self.filepath_fetcher = filepath_fetcher
        self.success_callback = success_callback
        self.failure_callback = failure_callback

    def get_filepath(self) -> str | None:
        """
        Grabs the filepath.
        :return: The filepath of the file to send.
        """
        if self.filepath_fetcher is None:
            return None

        if self.filepath is None:
            temp_filepath = self.filepath_fetcher(self.journal_code, self.article_id)
            if temp_filepath is None:
                return None

            self.filename = os.path.basename(temp_filepath)
            self.file_folder = self.prepare_temp_folder(temp_filepath)
            logger.debug(
                f"\nPrepared file from ::: Original File Path: {temp_filepath}\nFile Name: {self.filename}\nFile Folder: {self.file_folder}")
            if self.file_folder is None:
                return None
            self.filepath = os.path.join(self.file_folder, self.filename)

        return self.filepath

    def success(self) -> None:
        """
        Call when the file is successfully transferred.
        """
        if self.success_callback is None:
            return
        self.success_callback(self.journal_code, self.article_id)

    def failure(self, error_message: str | None = None, error: Exception | None = None) -> None:
        """
        Call when the file is not successfully transferred.
        """
        if self.failure_callback is None:
            return
        self.failure_callback(self.journal_code, self.article_id, error_message, error)

    def get_filename(self) -> str | None:
        """
        Gets the name of the file.
        :return: The name of the file, or None if the file does not exist.
        """
        if self.get_filepath() is None:
            return None

        return self.filename

    def prepare_temp_folder(self, filepath: str) -> str | None:
        temp_deposit_folder, zipped_file_name = deposit_helpers.prepare_temp_folder(
                request=self.request,
                article=self.article,
        )

        success = file_utils.copy_files_to_temp_deposit_folder(filepath, temp_deposit_folder)
        if not success:
            logger.debug(f"Could not copy files from {filepath} -> {temp_deposit_folder}")
            return None

        return temp_deposit_folder


class DefaultFilePreparer(FilePreparer):
    """
    Handles the default zip pathways.
    """

    def __init__(self, journal: Journal, article: Article, request):
        FilePreparer.__init__(self, journal, article, request, None, None, None)

    def get_filepath(self) -> str | None:
        # Create a temp folder
        temp_deposit_folder, zipped_file_name = deposit_helpers.prepare_temp_folder(
                request=self.request,
                article=self.article,
        )

        # Generate JATS stub
        deposit_helpers.generate_jats_metadata(
                article=self.article,
                article_folder=temp_deposit_folder,
        )

        # Copy all files into folder
        file_utils.copy_article_files(
                article=self.article,
                temp_deposit_folder=temp_deposit_folder,
        )

        # Zip Folder
        zipped_file_path = deposit_helpers.zip_temp_folder(
                temp_folder=temp_deposit_folder,
        )

        return zipped_file_path
