from pydoc import locate
from typing import Callable, Union, Any, Optional

from django.core.exceptions import ObjectDoesNotExist
from utils.logger import get_logger

from utils.setting_handler import get_setting as get_setting_handler
from journal.models import Journal

logger = get_logger(__name__)

PLUGIN_SETTINGS_GROUP_NAME = "plugin"


def get_transfer_file_function(function_path: str) -> Callable[[str, str], Union[str, None]]:
    """
    Gets the callable for the function in a setting.
    :param function_path: The path of the settings file.
    :return: The callable.
    """
    func: Optional[Callable[[str, str], Union[str, None]]] = locate(function_path)  # type: ignore
    if func is None:
        raise ImportError(f"Cannot locate {function_path}")
    return func


def get_setting(setting_name: str, journal: Journal) -> Any | None:
    """
    Gets the setting for the given setting name.
    :param setting_name: The name of the setting to get the value for.
    :param journal: The journal to get the settings value for.
    :return: The value for the given setting or a blank string, if the process failed.
    """
    try:
        return get_setting_handler(setting_group_name=PLUGIN_SETTINGS_GROUP_NAME,
                                           setting_name=setting_name, journal=journal, ).processed_value
    except ObjectDoesNotExist:
        logger.error("Could not get the following setting, '{0}'".format(setting_name))
        return None

class ZipFileSettings:
    """
    A settings class to track the ZIP file settings.
    """

    def __init__(self, journal: Journal):
        self.journal = journal
        self.is_enabled: bool = self.__get_is_enabled()
        self.function_path: str = self.__get_function_path()
        self.custom_function: Callable[[str, str], Union[str, None]] = self.__get_custom_function()
        self.success_callback: Callable[[str, str], Union[str, None]] = self.__get_success_callback()
        self.failure_callback: Callable[[str, str], Union[str, None]] = self.__get_failure_callback()

    def __get_function_path(self) -> str:
        """
        Gets the path to the function which fetches the file path.
        :return: The function to get the file path.
        """
        return get_setting('file_transfer_zip_function', self.journal)

    def __get_custom_function(self) -> Callable[[str, str], Union[str, None]]:
        """
        Gets the path to the function which fetches the file path.
        :return: The function to get the file path.
        """
        function_path: str = get_setting('file_transfer_zip_function', self.journal)
        if not function_path:
            return None
        return get_transfer_file_function(function_path)

    def __get_success_callback(self) -> Callable[[str, str], Union[str, None]]:
        """
        Gets the path to the function to call when the file transfer goes successfully.
        :return: The function to the success callback.
        """
        function_path: str = get_setting('file_transfer_zip_success_callback', self.journal)
        if not function_path:
            return None
        return get_transfer_file_function(function_path)

    def __get_failure_callback(self) -> Callable[[str, str], Union[str, None]]:
        """
        Gets the path to the function to call when the file transfer fails.
        :return: The function to the failure callback.
        """
        function_path: str = get_setting('file_transfer_zip_failure_callback', self.journal)
        if not function_path:
            return None
        return get_transfer_file_function(function_path)

    def __get_is_enabled(self) -> bool:
        is_enabled = get_setting("enable_transport_custom_zip", self.journal)
        if not is_enabled:
            return False
        return is_enabled



class GoFileSettings:
    """
    A settings class to track the Go XML file settings.
    """

    def __init__(self, journal: Journal):
        self.journal = journal
        self.is_enabled: bool = self.__get_is_enabled()
        self.function_path: str = self.__get_function_path()
        self.custom_function: Callable[[str, str], Union[str, None]] = self.__get_custom_function()
        self.success_callback: Callable[[str, str], Union[str, None]] = self.__get_success_callback()
        self.failure_callback: Callable[[str, str], Union[str, None]] = self.__get_failure_callback()

    def __get_function_path(self) -> str:
        """
        Gets the path to the function which fetches the file path.
        :return: The function to get the file path.
        """
        return get_setting('file_transfer_go_function', self.journal)

    def __get_custom_function(self) -> Callable[[str, str], Union[str, None]]:
        """
        Gets the path to the function which fetches the file path.
        :return: The function to get the file path.
        """
        function_path: str = get_setting('file_transfer_go_function', self.journal)
        if not function_path:
            return None
        return get_transfer_file_function(function_path)

    def __get_success_callback(self) -> Callable[[str, str], Union[str, None]]:
        """
        Gets the path to the function to call when the file transfer goes successfully.
        :return: The function to the success callback.
        """
        function_path: str = get_setting('file_transfer_go_success_callback', self.journal)
        if not function_path:
            return None
        return get_transfer_file_function(function_path)

    def __get_failure_callback(self) -> Callable[[str, str], Union[str, None]]:
        """
        Gets the path to the function to call when the file transfer fails.
        :return: The function to the failure callback.
        """
        function_path: str = get_setting('file_transfer_go_failure_callback', self.journal)
        if not function_path:
            return None
        return get_transfer_file_function(function_path)

    def __get_is_enabled(self) -> bool:
        is_enabled = get_setting("enable_transport_custom_go_xml", self.journal)
        if not is_enabled:
            return False
        return is_enabled


class ProductionTransporterSettings:
    def __init__(self, journal: Journal):
        self.journal: Journal = journal
        self.ftp_server: str = self.__get_ftp_server()
        self.ftp_username: str = self.__get_ftp_username()
        self.ftp_password: str = self.__get_ftp_password()
        self.ftp_remote_directory: str = self.__get_ftp_remote_directory()
        self.transport_enabled: bool = self.__get_transport_enabled()
        self.transport_production_stage: str = self.__get_transport_production_stage()
        self.production_contact_email: str = self.__get_production_contact_email()
        self.enable_transport_custom_files: bool = self.__get_enable_transport_custom_files()

        # More complex settings.
        self.custom_zip_settings: ZipFileSettings = ZipFileSettings(self.journal)
        self.custom_go_settings: GoFileSettings = GoFileSettings(self.journal)

    def __get_ftp_server(self) -> str:
        return self.__get_setting("transport_ftp_address")

    def __get_ftp_username(self) -> str:
        return self.__get_setting("transport_ftp_username")

    def __get_ftp_password(self) -> str:
        return self.__get_setting("transport_ftp_password")

    def __get_ftp_remote_directory(self) -> str:
        return self.__get_setting("transport_ftp_remote_path")

    def __get_production_contact_email(self) -> str:
        return self.__get_setting("transport_production_manager")

    def __get_transport_enabled(self) -> bool:
        return self.__get_setting("enable_transport")
    
    def __get_transport_production_stage(self) -> str:
        return self.__get_setting("transport_production_stage")

    def __get_enable_transport_custom_files(self) -> bool:
        return self.__get_setting("enable_transport_custom_zip")

    def __get_setting(self, settings_name: str) -> Any:
        return get_setting(settings_name, self.journal)
