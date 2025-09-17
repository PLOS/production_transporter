import shutil

from janeway_ftp import helpers as deposit_helpers

from submission.models import Article
from utils.logger import get_logger

logger = get_logger(__name__)


def copy_article_files(article: Article, temp_deposit_folder):
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


def copy_files_to_temp_deposit_folder(filepath: str, temp_deposit_folder: str) -> bool:
    try:
        shutil.copy(filepath, temp_deposit_folder)
    except FileNotFoundError as e:
        logger.debug(f"Could not find file {filepath} to copy: {e}")
        return False
    return True
