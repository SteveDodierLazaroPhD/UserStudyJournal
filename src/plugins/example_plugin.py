# from src import common # For common functions used by journal
# from src import supporting_widgets to use the non view related widgets journal uses throughout


__plugin_name__ = "Example Plugin"
# Enter a detailed description here
__description__ = "An example plugin, which does nothing important"


def activate(client, store, window):
    """
    This function is called to activate the plugin.

    :param client: the zeitgeist client used by journal
    :param store: the date based store which is used by journal to handle event and content object request
    :param window: the activity journal primary window
    """
    print "Activate"


def deactivate(client, store, window):
    """
    This function is called to activate the plugin.

    :param client: the zeitgeist client used by journal
    :param store: the date based store which is used by journal to handle event and content object request
    :param window: the activity journal primary window
    """
    print "Deactivate"
