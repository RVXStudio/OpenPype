import json
import maya.cmds as cmds
import maya.mel as mel

import copy
import clique

from openpype.pipeline.publish import (
    KnownPublishError,
    get_publish_template_name,
)
from openpype.client.operations import (
    OperationsSession,
    new_subset_document,
    new_version_doc,
    new_representation_doc,
    prepare_subset_update_data,
    prepare_version_update_data,
    prepare_representation_update_data,
)

from openpype.client import (
    get_representations,
    get_subset_by_name,
    get_version_by_name,
)
import pyblish.api
from openpype.pipeline import publish
import os

# import rvx-specific stuff
import rvx_usd
import rvx_ayon


class CollectUSDAssembly(pyblish.api.ContextPlugin):
    label = "[RVX] collect usd assembly"
    order = pyblish.api.CollectorOrder + 0.05
    hosts = ['maya']
    families = ['model']

    def process(self, context):
        # self.log.info(context.data.keys())
        self.log.info('starting collection')
        the_asset = context.data['asset']
        interesting_instances = {'render': False, 'proxy': False, 'guide': False}
        # find the interesting isntances in the current asset (in the case we are publishing all over the place)
        for instance in context:
            if instance.data['asset'] != the_asset:
                # if we are publishing outside our _current_ asset
                continue
            for k in interesting_instances.keys():
                if instance.data.get('variant', '').lower() == k:
                    interesting_instances[k] = True
                    break
        # assert that there are three purposes in the file
        if not all(interesting_instances.values()):
            self.log.warning(f"Some purposes seem to be missing: the missing purposes wil be fetched from db [{interesting_instances}]")

        assembly_instance = context.create_instance('usd_assembly', family='assembly')
        assembly_instance.data['asset'] = the_asset
        assembly_instance.data['subset'] = 'assemblyMain'
        assembly_instance.data['purpose_instances'] = interesting_instances
        assembly_instance.data['setMembers'] = [True]  # this is just to fool some validator down the line
        assembly_instance.data['usd_assembly_instances'] = interesting_instances
        self.log.info(f'Collectin usd assembly {interesting_instances}')


def get_frame_padded(frame, padding):
    """Return frame number as string with `padding` amount of padded zeros"""
    return "{frame:0{padding}d}".format(padding=padding, frame=frame)


def get_instance_families(instance):
    """Get all families of the instance"""
    # todo: move this to lib?
    family = instance.data.get("family")
    families = []
    if family:
        families.append(family)

    for _family in (instance.data.get("families") or []):
        if _family not in families:
            families.append(_family)

    return families


class ExtractUSDAssembly(publish.Extractor):

    label = "Extract USD assembly"
    hosts = ["maya"]
    families = ["assembly"]
    scene_type = "ma"
    optional = True
    order = pyblish.api.ExtractorOrder + 0.05

    default_template_name = "publish"
    db_representation_context_keys = [
        "project", "asset", "task", "subset", "version", "representation",
        "family", "hierarchy", "username", "user", "output"
    ]

    def process(self, instance):
        self.log.info(f'extracting {instance}')

        # first, check if the purposes are being published, and if not
        # we need to get the latest version of those purposes

        # we have already checked (when collecting) if the current workfile
        # has the purposes at all
        purpose_instances = {}
        parent_dir = self.staging_dir(instance)
        filename = "{name}.usda".format(**instance.data)
        usd_assembly_path = os.path.join(parent_dir, filename)
        self.log.info(f'outputting usd assembly: [{usd_assembly_path}]')
        for purpose_name, do_pub in instance.data['usd_assembly_instances'].items():
            self.log.info(f'looping {purpose_name}, {do_pub}')
            other_instance = None
            for inst in instance.context:
                if inst.data.get('variant', '').lower() == purpose_name:
                    self.log.info(f'{purpose_name} is doing pub: {do_pub}')
                    other_instance = inst
                    continue
            p_dict = {'instance': other_instance, 'is_publishing': do_pub}
            purpose_instances[purpose_name] = p_dict

        self.log.info(f'Ptime {purpose_instances}')

        usd_purpose_dict = {}
        for purpose_name, purpose_data in purpose_instances.items():
            if purpose_data.get('is_publishing', False):
                purpose_path = self.create_next_published_path(purpose_name, purpose_data)
            else:
                purpose_path = self.get_latest_published_path(purpose_name, instance)
            usd_purpose_dict[purpose_name] = purpose_path

        rvx_usd.create_purpose_assembly('tester', usd_purpose_dict, usd_assembly_path)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            "name": "usd",
            "ext": "usd",
            "files": filename,
            "stagingDir": parent_dir
        }
        instance.data["representations"].append(representation)
        self.log.info("Extracted {} to {}".format(instance, parent_dir))

    def get_latest_published_path(self, purpose_name, assembly_instance):
        self.log.info(f'Fetching latest published path for {purpose_name}')

        project_name = assembly_instance.context.data["projectName"]
        for k, v in assembly_instance.data.items():
            self.log.info(f'** {k}: {v}')
        folder_path = '{}/{}'.format(assembly_instance.data['anatomyData']['hierarchy'], assembly_instance.data['asset'])

        self.log.info(f'getting reps {folder_path}, {purpose_name}')
        usd_reps = rvx_ayon.get_usd_representations(project_name, folder_path, product_variants=[purpose_name])
        self.log.info(f'got {usd_reps}')

        usd_rep_path = usd_reps.get(purpose_name)
        if usd_rep_path is None:
            raise RuntimeError(f'No usd rep found for {purpose_name}')

        return usd_rep_path

    def create_next_published_path(self, purpose_name, data):
        self.log.info(f'creating next published path [{purpose_name}]')
        instance = data['instance']
        project_name = instance.context.data["projectName"]
        filtered_repres = [r for r in instance.data.get('representations', []) if r.get('name') == 'usd']

        instance_stagingdir = instance.data.get("stagingDir")
        if not instance_stagingdir:
            self.log.debug((
                "{0} is missing reference to staging directory."
                " Will try to get it from representation."
            ).format(instance))

        else:
            self.log.debug(
                "Establishing staging directory "
                "@ {0}".format(instance_stagingdir)
            )

        template_name = self.get_template_name(instance)
        op_session = OperationsSession()
        subset = self.prepare_subset(
            instance, op_session, project_name
        )
        version = self.prepare_version(
            instance, op_session, subset, project_name
        )

        # Get existing representations (if any)
        existing_repres_by_name = {
            repre_doc["name"].lower(): repre_doc
            for repre_doc in get_representations(
                project_name,
                version_ids=[version["_id"]],
                fields=["_id", "name"]
            )
        }

        # Prepare all representations
        for repre in filtered_repres:
            # todo: reduce/simplify what is returned from this function
            prepared = self.prepare_representation(
                repre,
                template_name,
                existing_repres_by_name,
                version,
                instance_stagingdir,
                instance)

            for k, v in prepared.items():
                self.log.info(f'Prepped {k}: {v}')

        prepped_files = prepared.get('published_files', [])
        assert len(prepped_files) > 0, "No prepped files!"
        return prepped_files[0]

    def prepare_subset(self, instance, op_session, project_name):
        asset_doc = instance.data["assetEntity"]
        subset_name = instance.data["subset"]
        family = instance.data["family"]
        self.log.debug("Subset: {}".format(subset_name))

        # Get existing subset if it exists
        existing_subset_doc = get_subset_by_name(
            project_name, subset_name, asset_doc["_id"]
        )

        # Define subset data
        data = {
            "families": get_instance_families(instance)
        }

        subset_group = instance.data.get("subsetGroup")
        if subset_group:
            data["subsetGroup"] = subset_group
        elif existing_subset_doc:
            # Preserve previous subset group if new version does not set it
            if "subsetGroup" in existing_subset_doc.get("data", {}):
                subset_group = existing_subset_doc["data"]["subsetGroup"]
                data["subsetGroup"] = subset_group

        subset_id = None
        if existing_subset_doc:
            subset_id = existing_subset_doc["_id"]
        subset_doc = new_subset_document(
            subset_name, family, asset_doc["_id"], data, subset_id
        )

        if existing_subset_doc is None:
            # Create a new subset
            self.log.info("Subset '%s' not found, creating ..." % subset_name)
            op_session.create_entity(
                project_name, subset_doc["type"], subset_doc
            )

        else:
            # Update existing subset data with new data and set in database.
            # We also change the found subset in-place so we don't need to
            # re-query the subset afterwards
            subset_doc["data"].update(data)
            update_data = prepare_subset_update_data(
                existing_subset_doc, subset_doc
            )
            op_session.update_entity(
                project_name,
                subset_doc["type"],
                subset_doc["_id"],
                update_data
            )

        self.log.debug("Prepared subset: {}".format(subset_name))
        return subset_doc

    def prepare_version(self, instance, op_session, subset_doc, project_name):
        version_number = instance.data["version"]

        existing_version = get_version_by_name(
            project_name,
            version_number,
            subset_doc["_id"],
            fields=["_id"]
        )
        version_id = None
        if existing_version:
            version_id = existing_version["_id"]

        version_data = self.create_version_data(instance)
        version_doc = new_version_doc(
            version_number,
            subset_doc["_id"],
            version_data,
            version_id
        )

        if existing_version:
            self.log.debug("Updating existing version ...")
            update_data = prepare_version_update_data(
                existing_version, version_doc
            )
            op_session.update_entity(
                project_name,
                version_doc["type"],
                version_doc["_id"],
                update_data
            )
        else:
            self.log.debug("Creating new version ...")
            op_session.create_entity(
                project_name, version_doc["type"], version_doc
            )

        self.log.debug(
            "Prepared version: v{0:03d}".format(version_doc["name"])
        )

        return version_doc

    def get_template_name(self, instance):
        """Return anatomy template name to use for integration"""

        # Anatomy data is pre-filled by Collectors
        context = instance.context
        project_name = context.data["projectName"]

        # Task can be optional in anatomy data
        host_name = context.data["hostName"]
        anatomy_data = instance.data["anatomyData"]
        family = anatomy_data["family"]
        task_info = anatomy_data.get("task") or {}

        return get_publish_template_name(
            project_name,
            host_name,
            family,
            task_name=task_info.get("name"),
            task_type=task_info.get("type"),
            project_settings=context.data["project_settings"],
            logger=self.log
        )

    def create_version_data(self, instance):
        """Create the data dictionary for the version

        Args:
            instance: the current instance being published

        Returns:
            dict: the required information for version["data"]
        """

        context = instance.context

        # create relative source path for DB
        if "source" in instance.data:
            source = instance.data["source"]
        else:
            source = context.data["currentFile"]
            anatomy = instance.context.data["anatomy"]
            source = self.get_rootless_path(anatomy, source)
        self.log.debug("Source: {}".format(source))

        version_data = {
            "families": get_instance_families(instance),
            "time": context.data["time"],
            "author": context.data["user"],
            "source": source,
            "comment": instance.data["comment"],
            "machine": context.data.get("machine"),
            "fps": instance.data.get("fps", context.data.get("fps"))
        }

        # todo: preferably we wouldn't need this "if dict" etc. logic and
        #       instead be able to rely what the input value is if it's set.
        intent_value = context.data.get("intent")
        if intent_value and isinstance(intent_value, dict):
            intent_value = intent_value.get("value")

        if intent_value:
            version_data["intent"] = intent_value

        # Include optional data if present in
        optionals = [
            "frameStart", "frameEnd", "step",
            "handleEnd", "handleStart", "sourceHashes"
        ]
        for key in optionals:
            if key in instance.data:
                version_data[key] = instance.data[key]

        # Include instance.data[versionData] directly
        version_data_instance = instance.data.get("versionData")
        if version_data_instance:
            version_data.update(version_data_instance)

        return version_data

    def get_rootless_path(self, anatomy, path):
        """Returns, if possible, path without absolute portion from root
            (eg. 'c:\' or '/opt/..')

         This information is platform dependent and shouldn't be captured.
         Example:
             'c:/projects/MyProject1/Assets/publish...' >
             '{root}/MyProject1/Assets...'

        Args:
            anatomy: anatomy part from instance
            path: path (absolute)
        Returns:
            path: modified path if possible, or unmodified path
            + warning logged
        """

        success, rootless_path = anatomy.find_root_template_from_path(path)
        if success:
            path = rootless_path
        else:
            self.log.warning((
                "Could not find root path for remapping \"{}\"."
                " This may cause issues on farm."
            ).format(path))
        return path

    def prepare_representation(self, repre,
                               template_name,
                               existing_repres_by_name,
                               version,
                               instance_stagingdir,
                               instance):

        # pre-flight validations
        if repre["ext"].startswith("."):
            raise KnownPublishError((
                "Extension must not start with a dot '.': {}"
            ).format(repre["ext"]))

        if repre.get("transfers"):
            raise KnownPublishError((
                "Representation is not allowed to have transfers"
                "data before integration. They are computed in "
                "the integrator. Got: {}"
            ).format(repre["transfers"]))

        # create template data for Anatomy
        template_data = copy.deepcopy(instance.data["anatomyData"])

        # required representation keys
        files = repre["files"]
        template_data["representation"] = repre["name"]
        template_data["ext"] = repre["ext"]

        # allow overwriting existing version
        template_data["version"] = version["name"]

        # add template data for colorspaceData
        if repre.get("colorspaceData"):
            colorspace = repre["colorspaceData"]["colorspace"]
            # replace spaces with underscores
            # pipeline.colorspace.parse_colorspace_from_filepath
            # is checking it with underscores too
            colorspace = colorspace.replace(" ", "_")
            template_data["colorspace"] = colorspace

        stagingdir = repre.get("stagingDir")
        if not stagingdir:
            # Fall back to instance staging dir if not explicitly
            # set for representation in the instance
            self.log.debug((
                "Representation uses instance staging dir: {}"
            ).format(instance_stagingdir))
            stagingdir = instance_stagingdir

        if not stagingdir:
            raise KnownPublishError(
                "No staging directory set for representation: {}".format(repre)
            )

        # optionals
        # retrieve additional anatomy data from representation if exists
        for key, anatomy_key in {
            # Representation Key: Anatomy data key
            "resolutionWidth": "resolution_width",
            "resolutionHeight": "resolution_height",
            "fps": "fps",
            "outputName": "output",
            "originalBasename": "originalBasename"
        }.items():
            # Allow to take value from representation
            # if not found also consider instance.data
            value = repre.get(key)
            if value is None:
                value = instance.data.get(key)

            if value is not None:
                template_data[anatomy_key] = value

        self.log.debug("Anatomy template name: {}".format(template_name))
        anatomy = instance.context.data["anatomy"]
        publish_template_category = anatomy.templates[template_name]
        template = os.path.normpath(publish_template_category["path"])

        is_udim = bool(repre.get("udim"))

        # handle publish in place
        if "{originalDirname}" in template:
            # store as originalDirname only original value without project root
            # if instance collected originalDirname is present, it should be
            # used for all represe
            # from temp to final
            original_directory = (
                instance.data.get("originalDirname") or instance_stagingdir)

            _rootless = self.get_rootless_path(anatomy, original_directory)
            if _rootless == original_directory:
                raise KnownPublishError((
                        "Destination path '{}' ".format(original_directory) +
                        "must be in project dir"
                ))
            relative_path_start = _rootless.rfind('}') + 2
            without_root = _rootless[relative_path_start:]
            template_data["originalDirname"] = without_root

        is_sequence_representation = isinstance(files, (list, tuple))
        self._validate_repre_files(files, is_sequence_representation)

        # Output variables of conditions below:
        # - transfers (List[Tuple[str, str]]): src -> dst filepaths to copy
        # - repre_context (Dict[str, Any]): context data used to fill template
        # - template_data (Dict[str, Any]): source data used to fill template
        #   - to add required data to 'repre_context' not used for
        #       formatting
        path_template_obj = anatomy.templates_obj[template_name]["path"]

        # Treat template with 'orignalBasename' in special way
        if "{originalBasename}" in template:
            # Remove 'frame' from template data
            template_data.pop("frame", None)

            # Find out first frame string value
            first_index_padded = None
            if not is_udim and is_sequence_representation:
                col = clique.assemble(files)[0][0]
                sorted_frames = tuple(sorted(col.indexes))
                # First frame used for end value
                first_frame = sorted_frames[0]
                # Get last frame for padding
                last_frame = sorted_frames[-1]
                # Use padding from collection of length of last frame as string
                padding = max(col.padding, len(str(last_frame)))
                first_index_padded = get_frame_padded(
                    frame=first_frame,
                    padding=padding
                )

            # Convert files to list for single file as remaining part is only
            #   transfers creation (iteration over files)
            if not is_sequence_representation:
                files = [files]

            repre_context = None
            transfers = []
            for src_file_name in files:
                template_data["originalBasename"], _ = os.path.splitext(
                    src_file_name)

                dst = path_template_obj.format_strict(template_data)
                src = os.path.join(stagingdir, src_file_name)
                transfers.append((src, dst))
                if repre_context is None:
                    repre_context = dst.used_values

            if not is_udim and first_index_padded is not None:
                repre_context["frame"] = first_index_padded

        elif is_sequence_representation:
            # Collection of files (sequence)
            src_collections, remainders = clique.assemble(files)

            src_collection = src_collections[0]
            destination_indexes = list(src_collection.indexes)
            # Use last frame for minimum padding
            #   - that should cover both 'udim' and 'frame' minimum padding
            destination_padding = len(str(destination_indexes[-1]))
            if not is_udim:
                # Change padding for frames if template has defined higher
                #   padding.
                template_padding = int(
                    publish_template_category["frame_padding"]
                )
                if template_padding > destination_padding:
                    destination_padding = template_padding

                # If the representation has `frameStart` set it renumbers the
                # frame indices of the published collection. It will start from
                # that `frameStart` index instead. Thus if that frame start
                # differs from the collection we want to shift the destination
                # frame indices from the source collection.
                # In case source are published in place we need to
                # skip renumbering
                repre_frame_start = repre.get("frameStart")
                if repre_frame_start is not None:
                    index_frame_start = int(repre_frame_start)
                    # Shift destination sequence to the start frame
                    destination_indexes = [
                        index_frame_start + idx
                        for idx in range(len(destination_indexes))
                    ]

            # To construct the destination template with anatomy we require
            # a Frame or UDIM tile set for the template data. We use the first
            # index of the destination for that because that could've shifted
            # from the source indexes, etc.
            first_index_padded = get_frame_padded(
                frame=destination_indexes[0],
                padding=destination_padding
            )

            # Construct destination collection from template
            repre_context = None
            dst_filepaths = []
            for index in destination_indexes:
                if is_udim:
                    template_data["udim"] = index
                else:
                    template_data["frame"] = index
                template_filled = path_template_obj.format_strict(
                    template_data
                )
                dst_filepaths.append(template_filled)
                if repre_context is None:
                    self.log.debug(
                        "Template filled: {}".format(str(template_filled))
                    )
                    repre_context = template_filled.used_values

            # Make sure context contains frame
            # NOTE: Frame would not be available only if template does not
            #   contain '{frame}' in template -> Do we want support it?
            if not is_udim:
                repre_context["frame"] = first_index_padded

            # Update the destination indexes and padding
            dst_collection = clique.assemble(dst_filepaths)[0][0]
            dst_collection.padding = destination_padding
            if len(src_collection.indexes) != len(dst_collection.indexes):
                raise KnownPublishError((
                    "This is a bug. Source sequence frames length"
                    " does not match integration frames length"
                ))

            # Multiple file transfers
            transfers = []
            for src_file_name, dst in zip(src_collection, dst_collection):
                src = os.path.join(stagingdir, src_file_name)
                transfers.append((src, dst))

        else:
            # Single file
            # Manage anatomy template data
            template_data.pop("frame", None)
            if is_udim:
                template_data["udim"] = repre["udim"][0]
            # Construct destination filepath from template
            template_filled = path_template_obj.format_strict(template_data)
            repre_context = template_filled.used_values
            dst = os.path.normpath(template_filled)

            # Single file transfer
            src = os.path.join(stagingdir, files)
            transfers = [(src, dst)]

        # todo: Are we sure the assumption each representation
        #       ends up in the same folder is valid?
        if not instance.data.get("publishDir"):
            template_obj = anatomy.templates_obj[template_name]["folder"]
            template_filled = template_obj.format_strict(template_data)
            instance.data["publishDir"] = template_filled

        for key in self.db_representation_context_keys:
            # Also add these values to the context even if not used by the
            # destination template
            value = template_data.get(key)
            if value is not None:
                repre_context[key] = value

        # Explicitly store the full list even though template data might
        # have a different value because it uses just a single udim tile
        if repre.get("udim"):
            repre_context["udim"] = repre.get("udim")  # store list

        # Use previous representation's id if there is a name match
        existing = existing_repres_by_name.get(repre["name"].lower())
        repre_id = None
        if existing:
            repre_id = existing["_id"]

        # Store first transferred destination as published path data
        # - used primarily for reviews that are integrated to custom modules
        # TODO we should probably store all integrated files
        #   related to the representation?
        published_path = transfers[0][1]
        repre["published_path"] = published_path

        # todo: `repre` is not the actual `representation` entity
        #       we should simplify/clarify difference between data above
        #       and the actual representation entity for the database
        data = repre.get("data", {})
        data.update({"path": published_path, "template": template})

        # add colorspace data if any exists on representation
        if repre.get("colorspaceData"):
            data["colorspaceData"] = repre["colorspaceData"]

        repre_doc = new_representation_doc(
            repre["name"], version["_id"], repre_context, data, repre_id
        )
        update_data = None
        if repre_id is not None:
            update_data = prepare_representation_update_data(
                existing, repre_doc
            )

        return {
            "representation": repre_doc,
            "repre_doc_update_data": update_data,
            "anatomy_data": template_data,
            "transfers": transfers,
            # todo: avoid the need for 'published_files' used by Integrate Hero
            # backwards compatibility
            "published_files": [transfer[1] for transfer in transfers]
        }

    def _validate_repre_files(self, files, is_sequence_representation):
        """Validate representation files before transfer preparation.

        Check if files contain only filenames instead of full paths and check
        if sequence don't contain more than one sequence or has remainders.

        Args:
            files (Union[str, List[str]]): Files from representation.
            is_sequence_representation (bool): Files are for sequence.

        Raises:
            KnownPublishError: If validations don't pass.
        """

        if not files:
            return

        if not is_sequence_representation:
            files = [files]

        if any(os.path.isabs(fname) for fname in files):
            raise KnownPublishError("Given file names contain full paths")

        if not is_sequence_representation:
            return

        src_collections, remainders = clique.assemble(files)
        if len(files) < 2 or len(src_collections) != 1 or remainders:
            raise KnownPublishError((
                "Files of representation does not contain proper"
                " sequence files.\nCollected collections: {}"
                "\nCollected remainders: {}"
            ).format(
                ", ".join([str(col) for col in src_collections]),
                ", ".join([str(rem) for rem in remainders])
            ))
