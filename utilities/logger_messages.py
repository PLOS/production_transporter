def process_failed_no_article_id_provided() -> str:
    """
    Gets the log message for when an article ID was not provided.
    :return: The logger message.
    """
    return "No article ID provided. Discontinuing export process."


def process_failed_no_janeway_journal_code_provided() -> str:
    """
    Gets the log message for when no journal code was provided.
    :return: The logger message.
    """
    return "No Janeway journal code was provided. Discontinuing export process."


def process_failed_fetching_article(article_id: int) -> str:
    """
    Gets the log message for when an article failed to be fetched.
    :param: article_id: The ID of the article being fetched.
    :return: The logger message.
    """
    return "Fetching article from database (ID: {0}) failed. Discontinuing export process.".format(article_id)


def process_failed_fetching_journal(janeway_journal_code: str | None = None, article_id: int = None) -> str:
    """
    Gets the log message for when a journal failed to be fetched.
    :param: janeway_journal_code: The code of the journal being fetched.
    :param: article_id: (Optional) The ID of the article.
    :return: The logger message.
    """
    if not janeway_journal_code and not article_id:
        return process_failed_no_janeway_journal_code_provided()

    if article_id and not janeway_journal_code:
        return "Fetching journal from database where article (ID: {0}) lives failed. Discontinuing export process.".format(article_id)

    if not article_id:
        return "Fetching journal from database (Code: {0}) failed. Discontinuing export process.".format(
            janeway_journal_code)

    return "Fetching journal from database (Code: {0}) where article (ID: {1}) lives failed. Discontinuing export process.".format(
        janeway_journal_code, article_id)
