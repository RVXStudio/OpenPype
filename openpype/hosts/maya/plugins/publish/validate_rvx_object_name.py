import pyblish.api
import ayon_api
import maya.cmds as mc
import re

import openpype.hosts.maya.api.action
from openpype.pipeline.publish import ValidateContentsOrder
import rvx_maya.lib

class ValidateObjectName(pyblish.api.InstancePlugin):
    order = pyblish.api.ValidatorOrder

    hosts = ['maya']
    families = ['model']

    order = ValidateContentsOrder
    optional = True
    label = 'Validate object names'

    actions = [openpype.hosts.maya.api.action.SelectInvalidAction]
    pattern = None

    @classmethod
    def get_invalid(cls, instance):
        """Get invalid nodes in instance.

        Args:
            instance (:class:`pyblish.api.Instance`): published instance.

        """
        invalid = rvx_maya.lib.get_invalid_names(instance, top_nodes=instance.data.get('setMembers', []))
        # transforms = mc.ls(instance, type='transform', long=False)
        # # print('\n'.join(list(instance.data.keys())))
        # for i in instance.data.get('setMembers', []):
        #     print(f'INSTANCE: {i}')

        # invalid = []
        # for transform in transforms:
        #         shapes = mc.listRelatives(transform,
        #                                     shapes=True,
        #                                     fullPath=True,
        #                                     noIntermediate=True)

        #         shape_type = mc.nodeType(shapes[0]) if shapes else "group"

        #     if not cls.is_valid_name(transform, shape_type):
        #         invalid.append(transform) 
        return invalid

    @classmethod
    def is_valid_name(cls, transform, shape_type):
        return re.match(cls.pattern, transform) is not None

    def process(self, instance):
        """Process all the nodes in the instance.

        Args:
            instance (:class:`pyblish.api.Instance`): published instance.

        """

        # product_type = instance.data['family']
        # rvx_settings = ayon_api.get_addons_settings(instance.context.data['projectName'])
        # regex_list = rvx_settings['rvx']['maya']['PublishSettings']['ValidateObjectNameRegex']
        # for rl in regex_list:
        #     self.log.info(f'{product_type} vs {rl["product_type"]}')
        #     if product_type in rl['product_type']:
        #         self.__class__.pattern = rl['validation_regex']
        #         break
        # else:
        #     self.log.warning("no product found")
        #     return

        # self.log.info(f'regx {self.__class__.pattern}')
        invalid = self.get_invalid(instance)
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