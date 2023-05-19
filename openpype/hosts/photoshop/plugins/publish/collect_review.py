"""
Requires:
    None

Provides:
    instance     -> family ("review")
"""

import os

import pyblish.api

from openpype.pipeline.create import get_subset_name


class CollectReview(pyblish.api.ContextPlugin):
    """Adds review to families for instances marked to be reviewable.
    """

    label = "Collect Review"
    label = "Review"
    hosts = ["photoshop"]
    order = pyblish.api.CollectorOrder + 0.1

    publish = True

    def process(self, context):
<<<<<<< HEAD
        family = "review"
        subset = get_subset_name(
            family,
            context.data.get("variant", ''),
            context.data["anatomyData"]["task"]["name"],
            context.data["assetEntity"],
            context.data["anatomyData"]["project"]["name"],
            host_name=context.data["hostName"],
            project_settings=context.data["project_settings"]
        )

        instance = context.create_instance(subset)
        instance.data.update({
            "subset": subset,
            "label": subset,
            "name": subset,
            "family": family,
            "families": [],
            "representations": [],
            "asset": context.data["asset"],
            "publish": self.publish
        })
=======
        for instance in context:
            creator_attributes = instance.data["creator_attributes"]
            if (creator_attributes.get("mark_for_review") and
                    "review" not in instance.data["families"]):
                instance.data["families"].append("review")
>>>>>>> 5125b21b66b8cbceed4f227abe17b6d1088f5ec0
