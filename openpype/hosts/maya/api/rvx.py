import maya.cmds as mc
import json
import os
import logging

from openpype.hosts.maya.api.lib import evaluation

log = logging.getLogger(__name__)
_usd_options = {
    "startFrame": float,
    "endFrame": float,
    "frameRange": tuple,  # "start end"; overrides startFrame & endFrame
    "eulerFilter": bool,
    "frameRelativeSample": float,
    "noNormals": bool,
    "renderableOnly": bool,
    "step": float,
    "stripNamespaces": bool,
    "exportUVs": bool,
    "wholeFrameGeo": bool,
    "worldspace": bool,
    "writeVisibility": bool,
    "writeColorSets": bool,
    "writeFaceSets": bool,
    "writeCreases": bool,  # Maya 2015 Ext1+
    "writeUVSets": bool,   # Maya 2017+
    "dataFormat": str,
    "root": (list, tuple),
    "attr": (list, tuple),
    "attrPrefix": (list, tuple),
    "userAttr": (list, tuple),
    "melPerFrameCallback": str,
    "melPostJobCallback": str,
    "pythonPerFrameCallback": str,
    "pythonPostJobCallback": str,
    "selection": bool
}

def extract_usd(file,
                startFrame=None,
                endFrame=None,
                selection=True,
                roots=[],
                exportUVs=True,
                eulerFilter=True,
                verbose=False,
                **kwargs):

    # Ensure maya-usd is loaded
    mc.loadPlugin('mayaUsdPlugin', quiet=True)

    # we don't want any backward slashes
    file = file.replace('\\', '/')

    # Pass the start and end frame on as `frameRange` so that it
    # never conflicts with that argument
    if "frameRange" not in kwargs:
        # Fallback to maya timeline if no start or end frame provided.
        if startFrame is None:
            startFrame = mc.playbackOptions(query=True,
                                            animationStartTime=True)
        if endFrame is None:
            endFrame = mc.playbackOptions(query=True,
                                          animationEndTime=True)

        # Ensure valid types are converted to frame range
        print(startFrame, _usd_options['startFrame'])
        assert isinstance(startFrame, _usd_options["startFrame"])
        assert isinstance(endFrame, _usd_options["endFrame"])
        kwargs["frameRange"] = (startFrame, endFrame)
    else:
        # Allow conversion from tuple for `frameRange`
        frame_range = kwargs["frameRange"]
        if isinstance(frame_range, (list, tuple)):
            assert len(frame_range) == 2
            kwargs["frameRange"] = (frame_range[0], frame_range[1])

    # Assemble options
    options = {
        "selection": selection,
        "exportUVs": exportUVs,
        "eulerFilter": eulerFilter
    }
    options.update(kwargs)

    # Validate options
    for key, value in options.copy().items():

        # Discard unknown options
        if key not in _usd_options:
            log.warning("extract_usd() does not support option '%s'. "
                        "Flag will be ignored..", key)
            options.pop(key)
            continue

        # Validate value type
        valid_types = _usd_options[key]
        if not isinstance(value, valid_types):
            raise TypeError("Usd option unsupported type: "
                            "{0} (expected {1})".format(value, valid_types))

        # Ignore empty values, like an empty string, since they mess up how
        # job arguments are built
        if isinstance(value, (list, tuple)):
            try:
                value = [x for x in value if x.strip()]
            except AttributeError:
                value = [x for x in value]

            # Ignore option completely if no values remaining
            if not value:
                options.pop(key)
                continue

            options[key] = value

    options['file'] = file
    # we don't want no materials
    options['convertMaterialsTo'] = 'none'
    options['shadingMode'] = 'none'

    if not selection and len(roots) > 0:
        options['exportRoots'] = roots

    # Ensure output directory exists
    parent_dir = os.path.dirname(file)
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    if verbose:
        print("Preparing USD export with options: %s",
              json.dumps(options, indent=4))

    # Perform extraction
    print("USD Job Arguments : {}".format(options))

    # Disable the parallel evaluation temporarily to ensure no buggy
    # exports are made. (PLN-31)
    # TODO: Make sure this actually fixes the issues
    with evaluation("off"):
        mc.mayaUSDExport(**options)

    if verbose:
        log.debug("Extracted USD to: %s", file)

    return file