from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from journal.models import Journal
from plugins.production_transporter.utilities import logger_messages
from plugins.production_transporter.utilities.settings import ProductionTransporterSettings
from submission.models import Article
from utils import setting_handler
from utils.logger import get_logger

logger = get_logger(__name__)

CACHE_TIMEOUT = 300
SETTINGS_CACHE_TIMEOUT = CACHE_TIMEOUT * 3


def fetch_setting(journal: Journal, setting_group_name: str, setting_name: str, fetch_fresh: bool = False):
    """
    Fetches journal settings.
    :param journal: The journal whose settings should be fetched.
    :param setting_group_name: The setting group name.
    :param setting_name: The setting name.
    :param fetch_fresh: True if this should ignore the cache and fetch fresh.
    :return: The setting.
    """
    if fetch_fresh:
        setting = None
    else:
        setting = cache.get(f"setting_{setting_group_name}_{setting_name}", None)

    if setting is None:
        try:
            setting = setting_handler.get_setting(setting_group_name=setting_group_name,
                                                  setting_name=setting_name, journal=journal, ).processed_value
            cache.set(f"setting_{setting_group_name}_{setting_name}", setting, SETTINGS_CACHE_TIMEOUT)
        except ObjectDoesNotExist as e:
            logger.exception("Could not get the following setting, '{0}'".format(setting_name), e)
            return None

    return setting


def fetch_settings(journal: Journal | str | None = None,
                   fetch_fresh: bool = False) -> ProductionTransporterSettings | None:
    """
    Fetches the journal settings for the ProductionTransporter.
    :param journal: The journal whose settings should be fetched.
    :param fetch_fresh: True if this should ignore the cache and fetch fresh.
    :return: The settings for the given journal.
    """
    if not journal:
        return None

    if isinstance(journal, str):
        journal_code = journal
        journal = fetch_journal_data(journal)
        if not journal:
            logger.error(
                    f"Could not fetch journal data from database while getting settings, journal code: {journal_code}.")
            return None

    journal_code = journal.code

    if fetch_fresh:
        settings = None
    else:
        settings = cache.get(f"production_transporter_settings_service_{journal_code}", None)

    if not settings:
        settings = ProductionTransporterSettings(journal)
        cache.set(f"production_transporter_settings_service_{journal_code}", settings, SETTINGS_CACHE_TIMEOUT)

    return settings


def fetch_journal_data(journal_code: str | None, fetch_fresh: bool = False) -> Journal | None:
    """
    Fetches the journal from the cache, making more efficient calls.
    :param journal_code: The journal code
    :param fetch_fresh: True if this should ignore the cache and fetch fresh.
    :return: The journal if one was found, else None
    """
    if not journal_code:
        logger.error(logger_messages.process_failed_no_janeway_journal_code_provided())
        return None

    if fetch_fresh:
        journal = None
    else:
        journal = cache.get(f"journal_{journal_code}", None)

    if not journal:
        journal = Journal.objects.filter(code=journal_code).only("id", "code").first()
        if not journal:
            logger.error(logger_messages.process_failed_fetching_journal(journal_code))
            return None
        cache.set(f"journal_{journal_code}", journal, CACHE_TIMEOUT)

    return journal


def fetch_article(journal: Journal | None, article_id: int | str | None, fetch_fresh: bool = False) -> Article | None:
    """
    Fetches the article from the cache, making more efficient calls.
    :param journal: The journal where the article is located.
    :param article_id: The article id.
    :param fetch_fresh: True if this should ignore the cache and fetch fresh.
    :return: An article or None if the article was not found.
    """
    if not article_id:
        logger.error(logger_messages.process_failed_no_article_id_provided())
        return None

    if not journal:
        logger.error(logger_messages.process_failed_fetching_journal(article_id=article_id))
        return None

    if isinstance(article_id, str):
        try:
            article_id = int(article_id)
        except ValueError:
            logger.error(f"Could not convert article ID {article_id} to an integer.")
            return None

    if fetch_fresh:
        article = None
    else:
        article = cache.get(f"article_{article_id}", None)

    if not article:
        article = Article.objects.filter(id=article_id, journal=journal).defer("journal").first()
        if not article:
            logger.error(logger_messages.process_failed_fetching_article(article_id))
            return None

        cache.set(f"article_{article_id}", article, CACHE_TIMEOUT)

    return article
