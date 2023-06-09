import pyblish.api
import ayon_api
import maya.cmds as mc
import re

import openpype.hosts.maya.api.action
from openpype.pipeline.publish import ValidateContentsOrder


class ValidateObjectName(pyblish.api.InstancePlugin):
    order = pyblish.api.ValidatorOrder

    hosts = ['maya']
    families = ['model']

    order = ValidateContentsOrder
    optional = True
    label = 'Validate object names'

    actions = [openpype.hosts.maya.api.action.SelectInvalidAction]


    @classmethod
    def get_invalid(cls, instance, pattern):
        """Get invalid nodes in instance.

        Args:
            instance (:class:`pyblish.api.Instance`): published instance.

        """
        transforms = mc.ls(instance, type='transform', long=False)

        invalid = []
        for transform in transforms:
            if not cls.is_valid_name(transform, pattern):
                invalid.append(transform)
        return invalid

    @classmethod
    def is_valid_name(cls, transform, pattern):
        return re.match(pattern, transform) is not None

    def process(self, instance):
        """Process all the nodes in the instance.

        Args:
            instance (:class:`pyblish.api.Instance`): published instance.

        """
        product_type = instance.data['family']
        rvx_settings = ayon_api.get_addons_settings(instance.context.data['projectName'])
        regex_list = rvx_settings['rvx']['maya']['PublishSettings']['ValidateObjectNameRegex']
        for rl in regex_list:
            self.log.info(f'{product_type} vs {rl["product_type"]}')
            if product_type in rl['product_type']:
                the_regex = rl['validation_regex']
                break
        else:
            self.log.warning("no product found")
            return

        self.log.info(f'regx {the_regex}')
        invalid = self.get_invalid(instance, the_regex)
        if invalid:
            raise ValueError("Invalid names found (correct pattern: <location(optional)>_<geoDescription>_<variant>_<condition>_<instance>_<material>_<geoType>): {0}".format(invalid))
    '''
    @staticmethod
    def get_invalid(instance):

        objects = mc.ls(instance, type='transform', shortNames=True)

        for k,v in instance.data.items():
            print('!!', k, v)

        invalid = []
        for obj in objects:
            if obj in instance.data.get('set_members', []):
                print(f'Ignoring top-level set member {obj}')
                continue
            if not rvx_maya.lib.validate_object_name(obj, context=instance.data.get('family', 'no-familyt')):
                invalid.append(obj)
            # if (mc.polyInfo(mesh, nonManifoldVertices=True) or
            #         mc.polyInfo(mesh, nonManifoldEdges=True)):
            #     invalid.append(mesh)

        return invalid

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            raise ValueError("Invalid names found (correct pattern: <location(optional)>_<geoDescription>_<variant>_<condition>_<instance>_<material>_<geoType>): {0}".format(invalid))

            
        #for member in instance.data.get('set_members', []):
        #    assert member.endswith('_GRP'), 'All top-level groups need to end with _GRP!'
   
    '''