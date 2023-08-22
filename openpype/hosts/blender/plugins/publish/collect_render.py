# -*- coding: utf-8 -*-
"""Collect render data."""

import os
import re

import bpy

from openpype.pipeline import (
    get_current_project_name,
)
from openpype.settings import (
    get_project_settings,
)
from openpype.hosts.blender.api import colorspace
import pyblish.api


class CollectBlenderRender(pyblish.api.InstancePlugin):
    """Gather all publishable render layers from renderSetup."""

    order = pyblish.api.CollectorOrder + 0.01
    hosts = ["blender"]
    families = ["renderlayer"]
    label = "Collect Render Layers"
    sync_workfile_version = False

    @staticmethod
    def get_default_render_folder(settings):
        """Get default render folder from blender settings."""

        return (settings["blender"]
                        ["RenderSettings"]
                        ["default_render_image_folder"])

    @staticmethod
    def get_aov_separator(settings):
        """Get aov separator from blender settings."""

        aov_sep = (settings["blender"]
                           ["RenderSettings"]
                           ["aov_separator"])

        if aov_sep == "dash":
            return "-"
        elif aov_sep == "underscore":
            return "_"
        elif aov_sep == "dot":
            return "."
        else:
            raise ValueError(f"Invalid aov separator: {aov_sep}")

    @staticmethod
    def get_image_format(settings):
        """Get image format from blender settings."""

        return (settings["blender"]
                        ["RenderSettings"]
                        ["image_format"])

    @staticmethod
    def get_multilayer(settings):
        """Get multilayer from blender settings."""

        return (settings["blender"]
                        ["RenderSettings"]
                        ["multilayer_exr"])

    @staticmethod
    def get_render_product(output_path, instance):
        """
        Generate the path to the render product. Blender interprets the `#`
        as the frame number, when it renders.

        Args:
            file_path (str): The path to the blender scene.
            render_folder (str): The render folder set in settings.
            file_name (str): The name of the blender scene.
            instance (pyblish.api.Instance): The instance to publish.
            ext (str): The image format to render.
        """
        output_file = os.path.join(output_path, instance.name)

        render_product = f"{output_file}.####"
        render_product = render_product.replace("\\", "/")

        return render_product

    @staticmethod
    def generate_expected_beauty(
        render_product, frame_start, frame_end, frame_step, ext
    ):
        """
        Generate the expected files for the render product for the beauty
        render. This returns a list of files that should be rendered. It
        replaces the sequence of `#` with the frame number.
        """
        path = os.path.dirname(render_product)
        file = os.path.basename(render_product)

        expected_files = []

        for frame in range(frame_start, frame_end + 1, frame_step):
            frame_str = str(frame).rjust(4, "0")
            filename = re.sub("#+", frame_str, file)
            expected_file = f"{os.path.join(path, filename)}.{ext}"
            expected_files.append(expected_file.replace("\\", "/"))

        return {
            "beauty": expected_files
        }

    @staticmethod
    def generate_expected_aovs(
        aov_file_product, frame_start, frame_end, frame_step, ext
    ):
        """
        Generate the expected files for the render product for the beauty
        render. This returns a list of files that should be rendered. It
        replaces the sequence of `#` with the frame number.
        """
        expected_files = {}

        for aov_name, aov_file in aov_file_product:
            path = os.path.dirname(aov_file)
            file = os.path.basename(aov_file)

            aov_files = []

            for frame in range(frame_start, frame_end + 1, frame_step):
                frame_str = str(frame).rjust(4, "0")
                filename = re.sub("#+", frame_str, file)
                expected_file = f"{os.path.join(path, filename)}.{ext}"
                aov_files.append(expected_file.replace("\\", "/"))

            expected_files[aov_name] = aov_files

        return expected_files

    @staticmethod
    def set_render_format(ext, multilayer):
        # Set Blender to save the file with the right extension
        bpy.context.scene.render.use_file_extension = True

        image_settings = bpy.context.scene.render.image_settings

        if ext == "exr":
            image_settings.file_format = (
                "OPEN_EXR_MULTILAYER" if multilayer else "OPEN_EXR")
        elif ext == "bmp":
            image_settings.file_format = "BMP"
        elif ext == "rgb":
            image_settings.file_format = "IRIS"
        elif ext == "png":
            image_settings.file_format = "PNG"
        elif ext == "jpeg":
            image_settings.file_format = "JPEG"
        elif ext == "jp2":
            image_settings.file_format = "JPEG2000"
        elif ext == "tga":
            image_settings.file_format = "TARGA"
        elif ext == "tif":
            image_settings.file_format = "TIFF"

    def _create_context(self):
        context = bpy.context.copy()

        win = bpy.context.window_manager.windows[0]
        screen = win.screen
        area = screen.areas[0]
        region = area.regions[0]

        context["window"] = win
        context['screen'] = screen
        context['area'] = area
        context['region'] = region

        return context

    def set_node_tree(self, output_path, instance, aov_sep):
        # Set the scene to use the compositor node tree to render
        bpy.context.scene.use_nodes = True

        tree = bpy.context.scene.node_tree

        # Get the Render Layers node
        rl_node = None
        for node in tree.nodes:
            if node.bl_idname == "CompositorNodeRLayers":
                rl_node = node
                break

        # If there's not a Render Layers node, we create it
        if not rl_node:
            rl_node = tree.nodes.new("CompositorNodeRLayers")

        # Get the enabled output sockets, that are the active passes for the
        # render.
        # We also exclude some layers.
        exclude_sockets = ["Image", "Alpha"]
        passes = [
            socket
            for socket in rl_node.outputs
            if socket.enabled and socket.name not in exclude_sockets
        ]

        # Remove all output nodes
        for node in tree.nodes:
            if node.bl_idname == "CompositorNodeOutputFile":
                tree.nodes.remove(node)

        # Create a new output node
        output = tree.nodes.new("CompositorNodeOutputFile")

        context = self._create_context()
        context["node"] = output

        area = context["area"]

        # Change area type to node editor, to execute node operators
        old_area_type = area.ui_type
        area.ui_type = "CompositorNodeTree"

        # Remove the default input socket from the output node
        bpy.ops.node.output_file_remove_active_socket(context)

        output.base_path = output_path
        image_settings = bpy.context.scene.render.image_settings
        output.format.file_format = image_settings.file_format

        aov_file_products = []

        # For each active render pass, we add a new socket to the output node
        # and link it
        for render_pass in passes:
            filepath = f"{instance.name}{aov_sep}{render_pass.name}.####"
            bpy.ops.node.output_file_add_socket(context, file_path=filepath)

            aov_file_products.append(
                (render_pass.name, os.path.join(output_path, filepath)))

            node_input = output.inputs[-1]

            tree.links.new(render_pass, node_input)

        # Restore the area type
        area.ui_type = old_area_type

        return aov_file_products

    @staticmethod
    def set_render_camera(instance):
        # There should be only one camera in the instance
        found = False
        for obj in instance:
            if isinstance(obj, bpy.types.Object) and obj.type == "CAMERA":
                bpy.context.scene.camera = obj
                found = True
                break

        assert found, "No camera found in the render instance"

    def process(self, instance):
        context = instance.context

        filepath = context.data["currentFile"].replace("\\", "/")
        file_path = os.path.dirname(filepath)
        file_name = os.path.basename(filepath)
        file_name, _ = os.path.splitext(file_name)

        project = get_current_project_name()
        settings = get_project_settings(project)

        render_folder = self.get_default_render_folder(settings)
        aov_sep = self.get_aov_separator(settings)
        ext = self.get_image_format(settings)
        multilayer = self.get_multilayer(settings)

        output_path = os.path.join(file_path, render_folder, file_name)

        render_product = self.get_render_product(output_path, instance)
        aov_file_product = self.set_node_tree(output_path, instance, aov_sep)

        # We set the render path, the format and the camera
        bpy.context.scene.render.filepath = render_product
        self.set_render_format(ext, multilayer)
        self.set_render_camera(instance)

        # We save the file to save the render settings
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)

        frame_start = context.data["frameStart"]
        frame_end = context.data["frameEnd"]
        frame_handle_start = context.data["frameStartHandle"]
        frame_handle_end = context.data["frameEndHandle"]

        expected_beauty = self.generate_expected_beauty(
            render_product, int(frame_start), int(frame_end),
            int(bpy.context.scene.frame_step), ext)

        expected_aovs = self.generate_expected_aovs(
            aov_file_product, int(frame_start), int(frame_end),
            int(bpy.context.scene.frame_step), ext)

        expected_files = expected_beauty | expected_aovs

        instance.data.update({
            "frameStart": frame_start,
            "frameEnd": frame_end,
            "frameStartHandle": frame_handle_start,
            "frameEndHandle": frame_handle_end,
            "fps": context.data["fps"],
            "byFrameStep": bpy.context.scene.frame_step,
            "farm": True,
            "expectedFiles": [expected_files],
            # OCIO not currently implemented in Blender, but the following
            # settings are required by the schema, so it is hardcoded.
            # TODO: Implement OCIO in Blender
            "colorspaceConfig": "",
            "colorspaceDisplay": "sRGB",
            "colorspaceView": "ACES 1.0 SDR-video",
            "renderProducts": colorspace.ARenderProduct(),
        })

        self.log.info(f"data: {instance.data}")
