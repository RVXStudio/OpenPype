from maya import cmds
import pymel.core as pm

import pyblish.api
import avalon.api

class CollectAssData(pyblish.api.InstancePlugin):
    """Collect Ass data

    """

    order = pyblish.api.CollectorOrder + 0.2
    label = 'Collect Ass'
    families = ["ass"]

    def process(self, instance):


        context = instance.context

        objsets = instance.data['setMembers']

        for objset in objsets:
            members = cmds.sets(objset, query=True)
            if members is None:
                self.log.warning("Skipped empty instance: \"%s\" " % objset)
                continue
            if objset == "content_SET":
                instance.data['setMembers'] = members
            elif objset == "proxy_SET":
                assert len(members) == 1, "You have multiple proxy meshes, please only use one"
                instance.data['proxy'] = members


        self.log.debug("data: {}".format(instance.data))
