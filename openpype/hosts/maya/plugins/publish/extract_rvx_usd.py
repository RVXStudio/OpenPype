import os
import logging

from maya import cmds

from openpype.pipeline import publish
from openpype.hosts.maya.api.lib import (
    suspended_refresh,
    maintained_selection,
    iter_visible_nodes_in_range
)
from openpype.hosts.maya.api.rvx import (
    extract_usd
)

log = logging.getLogger(__name__)


class ExtractUSD(publish.Extractor):
    """Produce an alembic of just point positions and normals.

    Positions and normals, uvs, creases are preserved, but nothing more,
    for plain and predictable point caches.

    Plugin can run locally or remotely (on a farm - if instance is marked with
    "farm" it will be skipped in local processing, but processed on farm)
    """

    label = "Extract model USD"
    hosts = ["maya"]
    families = ["model"]
    targets = ["local", "remote"]

    def process(self, instance):
        if instance.data.get("farm"):
            self.log.debug("Should be processed on farm, skipping.")
            return

        nodes, roots = self.get_members_and_roots(instance)
        print('these are the roots:', roots)

        # Collect the start and end including handles
        start = float(instance.data.get("frameStartHandle", 1))
        end = float(instance.data.get("frameEndHandle", 1))

        attrs = instance.data.get("attr", "").split(";")
        attrs = [value for value in attrs if value.strip()]
        attrs += instance.data.get("userDefinedAttributes", [])
        attrs += ["cbId"]

        attr_prefixes = instance.data.get("attrPrefix", "").split(";")
        attr_prefixes = [value for value in attr_prefixes if value.strip()]

        self.log.info("Extracting pointcache..")
        dirname = self.staging_dir(instance)

        parent_dir = self.staging_dir(instance)
        filename = "{name}.usd".format(**instance.data)
        path = os.path.join(parent_dir, filename)

        options = {
            "exportUVs": True,
            "selection": False,
            "worldspace": instance.data.get("worldSpace", True)
        }

        self.log.info(f"INIT OPTIONS {options}")

        suspend = not instance.data.get("refresh", False)
        self.log.info(nodes)
        with suspended_refresh(suspend=suspend):
            with maintained_selection():
                # cmds.select(nodes, noExpand=True)
                extract_usd(
                    file=path,
                    startFrame=start,
                    endFrame=end,
                    roots=roots,
                    **options
                )

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            "name": "usd",
            "ext": "usd",
            "files": filename,
            "stagingDir": dirname
        }
        instance.data["representations"].append(representation)

        instance.context.data["cleanupFullPaths"].append(path)

        self.log.info("Extracted {} to {}".format(instance, dirname))

        # # Extract proxy.
        # if not instance.data.get("proxy"):
        #     self.log.info("No proxy nodes found. Skipping proxy extraction.")
        #     return

        # path = path.replace(".abc", "_proxy.abc")
        # if not instance.data.get("includeParentHierarchy", True):
        #     # Set the root nodes if we don't want to include parents
        #     # The roots are to be considered the ones that are the actual
        #     # direct members of the set
        #     options["root"] = instance.data["proxyRoots"]

        # with suspended_refresh(suspend=suspend):
        #     with maintained_selection():
        #         cmds.select(instance.data["proxy"])
        #         extract_alembic(
        #             file=path,
        #             startFrame=start,
        #             endFrame=end,
        #             **options
        #         )

        # representation = {
        #     "name": "proxy",
        #     "ext": "abc",
        #     "files": os.path.basename(path),
        #     "stagingDir": dirname,
        #     "outputName": "proxy"
        # }
        # instance.data["representations"].append(representation)

    def get_members_and_roots(self, instance):
        return instance[:], instance.data.get("setMembers")
