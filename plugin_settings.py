from utils import plugins
from utils.install import update_settings
from events import logic as events_logic
from plugins.production_transporter import utils

PLUGIN_NAME = 'Production Transporter'
DISPLAY_NAME = 'Production Transporter'
DESCRIPTION = 'Copies an article to an FTP server on acceptance.'
AUTHOR = 'Birkbeck, University of London'
VERSION = '0.1'
SHORT_NAME = 'production_transporter'
MANAGER_URL = 'production_transporter_manager'
JANEWAY_VERSION = "1.4.2"
IS_WORKFLOW_PLUGIN = True
HANDSHAKE_URL = 'production_transporter_handshake_url'
JUMP_URL = 'production_transporter_handshake_url'
ARTICLE_PK_IN_HANDSHAKE_URL = False
STAGE = 'production_transporter'


class ProductionTransporterPlugin(plugins.Plugin):
    plugin_name = PLUGIN_NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    author = AUTHOR
    short_name = SHORT_NAME
    manager_url = MANAGER_URL
    stage = STAGE

    version = VERSION
    janeway_version = JANEWAY_VERSION

    is_workflow_plugin = IS_WORKFLOW_PLUGIN
    handshake_url = HANDSHAKE_URL
    article_pk_in_handshake_url = ARTICLE_PK_IN_HANDSHAKE_URL
    jump_url = JUMP_URL


prod_transporter = ProductionTransporterPlugin()


def install():
    prod_transporter.install()
    update_settings(
        file_path='plugins/production_transporter/install/settings.json'
    )


def hook_registry():
    prod_transporter.hook_registry()


def register_for_events():
    events_logic.Events.register_for_event(
        events_logic.Events.ON_ARTICLE_ACCEPTED,
        utils.on_article_accepted,
    )
