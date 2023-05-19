import os
from openpype.pipeline import (
    load,
    get_representation_path
)
from openpype.hosts.max.api.pipeline import containerise
from openpype.hosts.max.api import lib


class FbxLoader(load.LoaderPlugin):
    """Fbx Loader"""

    families = ["camera"]
    representations = ["fbx"]
    order = -9
    icon = "code-fork"
    color = "white"

    def load(self, context, name=None, namespace=None, data=None):
        from pymxs import runtime as rt

        filepath = self.filepath_from_context(context)
        filepath = os.path.normpath(filepath)
<<<<<<< HEAD

        fbx_import_cmd = (
            f"""

FBXImporterSetParam "Animation" true
FBXImporterSetParam "Cameras" true
FBXImporterSetParam "AxisConversionMethod" true
FbxExporterSetParam "UpAxis" "Y"
FbxExporterSetParam "Preserveinstances" true

importFile @"{filepath}" #noPrompt using:FBXIMP
        """)

        self.log.debug(f"Executing command: {fbx_import_cmd}")
        rt.execute(fbx_import_cmd)

        container_name = f"{name}_CON"

        asset = rt.getNodeByName(f"{name}")
=======
        rt.FBXImporterSetParam("Animation", True)
        rt.FBXImporterSetParam("Camera", True)
        rt.FBXImporterSetParam("AxisConversionMethod", True)
        rt.FBXImporterSetParam("Preserveinstances", True)
        rt.importFile(
            filepath,
            rt.name("noPrompt"),
            using=rt.FBXIMP)

        container = rt.getNodeByName(f"{name}")
        if not container:
            container = rt.container()
            container.name = f"{name}"

        for selection in rt.getCurrentSelection():
            selection.Parent = container
>>>>>>> 5125b21b66b8cbceed4f227abe17b6d1088f5ec0

        return containerise(
            name, [container], context, loader=self.__class__.__name__)

    def update(self, container, representation):
        from pymxs import runtime as rt

        path = get_representation_path(representation)
        node = rt.getNodeByName(container["instance_node"])

        fbx_objects = self.get_container_children(node)
        for fbx_object in fbx_objects:
            fbx_object.source = path

        lib.imprint(container["instance_node"], {
            "representation": str(representation["_id"])
        })

    def remove(self, container):
        from pymxs import runtime as rt

        node = rt.getNodeByName(container["instance_node"])
        rt.delete(node)
