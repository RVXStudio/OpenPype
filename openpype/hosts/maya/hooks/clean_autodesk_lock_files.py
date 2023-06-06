import platform
import os
from openpype.lib import PreLaunchHook


class CleanAutodeskLockFiles(PreLaunchHook):
    """Check for those pesky autodesk lock files and remove them
    """
    app_groups = ["maya"]

    def execute(self):
        if platform.system() == 'Linux':
            try:
                lockfile = os.path.join(os.getenv('HOME'), '.config/Autodesk', 'Autodesk Licensing Manager.conf.lock')
                if os.path.exists(lockfile):
                    os.remove(lockfile)
            except Exception as err:
                self.log.error("Error removing lock file!", err)
            else:
                self.log.info("No lock file to remove!")
