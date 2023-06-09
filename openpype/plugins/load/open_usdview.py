
from openpype.lib import ApplicationManager
from openpype.pipeline import load


def existing_usdview_path():
    app_manager = ApplicationManager()
    usdview_list = []

    for app_name, app in app_manager.applications.items():
        if 'usdview' in app_name and app.find_executable():
            usdview_list.append(app_name)

    return usdview_list


class OpenInUsdview(load.LoaderPlugin):
    """Open Image Sequence with system default"""

    usdview_list = existing_usdview_path()
    families = ["*"] if usdview_list else []
    representations = ["*"]
    extensions = {
        "usd", "usda", "usdc"
    }

    label = "Open in usdview"
    order = -10
    icon = "play-circle"
    color = "orange"

    def load(self, context, name, namespace, data):

        path = self.filepath_from_context(context)

        self.log.info("Opening : {}".format(path))

        last_usdview_version = sorted(self.usdview_list)[-1]

        app_manager = ApplicationManager()
        usdview = app_manager.applications.get(last_usdview_version)
        usdview.arguments.append(path)

        app_manager.launch(last_usdview_version, project_name=context.get('project')['name'], asset_name=context.get('asset')['name'], task_name='')
