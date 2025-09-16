"""
This adds a class to handle the functionality of preparing files and any actions taken upon success or failure.
"""
from typing import Callable

from janeway_ftp import helpers as deposit_helpers
from journal.models import Journal
from plugins.production_transporter.utilities import file_utils
from submission.models import Article


class FilePreparer():
    def __init__(self, journal: Journal, article: Article, filepath_fetcher: Callable | None = None,
                 success_callback: Callable | None = None, failure_callback: Callable | None = None):
        self.journal = journal
        self.article = article
        self.journal_code = journal.code
        self.article_id = article.pk
        self.filepath: str | None = None
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
            self.filepath = self.filepath_fetcher(self.journal_code, self.article_id)
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


class DefaultFilePreparer(FilePreparer):
    """
    Handles the default zip pathways.
    """

    def __init__(self, journal: Journal, article: Article, request):
        self.request = request
        FilePreparer.__init__(self, journal, article, None, None, None)

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
