import json
import collections
import ftrack_api
from pype.modules.ftrack.lib import ServerAction


class PushFrameValuesToTaskAction(ServerAction):
    """Action for testing purpose or as base for new actions."""

    # Ignore event handler by default
    ignore_me = True

    identifier = "admin.push_frame_values_to_task"
    label = "Pype Admin"
    variant = "- Push Frame values to Task"

    hierarchy_entities_query = (
        "select id, parent_id from TypedContext where project_id is \"{}\""
    )
    entities_query = (
        "select id, name, parent_id, link from TypedContext"
        " where project_id is \"{}\" and object_type_id in ({})"
    )
    cust_attrs_query = (
        "select id, key, object_type_id, is_hierarchical, default"
        " from CustomAttributeConfiguration"
        " where key in ({})"
    )
    cust_attr_value_query = (
        "select value, entity_id from CustomAttributeValue"
        " where entity_id in ({}) and configuration_id in ({})"
    )

    # configurable
    interest_entity_types = ["Shot"]
    interest_attributes = ["frameStart", "frameEnd"]
    role_list = ["Pypeclub", "Administrator", "Project Manager"]

    def discover(self, session, entities, event):
        """ Validation """
        # Check if selection is valid
        for ent in event["data"]["selection"]:
            # Ignore entities that are not tasks or projects
            if ent["entityType"].lower() == "show":
                return True
        return False

    def launch(self, session, entities, event):
        self.log.debug("{}: Creating job".format(self.label))

        user_entity = session.query(
            "User where id is {}".format(event["source"]["user"]["id"])
        ).one()
        job = session.create("Job", {
            "user": user_entity,
            "status": "running",
            "data": json.dumps({
                "description": "Propagation of Frame attribute values to task."
            })
        })
        session.commit()

        try:
            project_entity = self.get_project_from_entity(entities[0])
            result = self.propagate_values(session, project_entity, event)
            job["status"] = "done"
            session.commit()

            return result

        except Exception:
            session.rollback()
            job["status"] = "failed"
            session.commit()

            msg = "Pushing Custom attribute values to task Failed"
            self.log.warning(msg, exc_info=True)
            return {
                "success": False,
                "message": msg
            }

        finally:
            if job["status"] == "running":
                job["status"] = "failed"
                session.commit()

    def attrs_configurations(self, session, object_ids):
        attrs = session.query(self.cust_attrs_query.format(
            self.join_query_keys(self.interest_attributes),
            self.join_query_keys(object_ids)
        )).all()

        output = {}
        hiearchical = []
        for attr in attrs:
            if attr["is_hierarchical"]:
                hiearchical.append(attr)
                continue
            obj_id = attr["object_type_id"]
            if obj_id not in output:
                output[obj_id] = []
            output[obj_id].append(attr)
        return output, hiearchical

    def join_keys(self, items):
        return ",".join(["\"{}\"".format(item) for item in items])

    def propagate_values(self, session, project_entity, event):
        self.log.debug("Querying project's entities \"{}\".".format(
            project_entity["full_name"]
        ))
        interest_entity_types = tuple(
            ent_type.lower()
            for ent_type in self.interest_entity_types
        )
        all_object_types = session.query("ObjectType").all()
        object_types_by_low_name = {
            object_type["name"].lower(): object_type
            for object_type in all_object_types
        }

        task_object_type = object_types_by_low_name["task"]
        destination_object_types = [task_object_type]
        for ent_type in interest_entity_types:
            obj_type = object_types_by_low_name.get(ent_type)
            if obj_type and obj_type not in destination_object_types:
                destination_object_types.append(obj_type)

        destination_object_type_ids = set(
            obj_type["id"]
            for obj_type in destination_object_types
        )

        # Find custom attributes definitions
        attrs_by_obj_id, hier_attrs = self.attrs_configurations(
            session, destination_object_type_ids
        )
        # Filter destination object types if they have any object specific
        # custom attribute
        for obj_id in tuple(destination_object_type_ids):
            if obj_id not in attrs_by_obj_id:
                destination_object_type_ids.remove(obj_id)

        if not destination_object_type_ids:
            # TODO report that there are not matching custom attributes
            return {
                "success": True,
                "message": "Nothing has changed."
            }

        entities = session.query(self.entities_query.format(
            project_entity["id"],
            self.join_query_keys(destination_object_type_ids)
        )).all()

        self.log.debug("Preparing whole project hierarchy by ids.")
        parent_id_by_entity_id = self.all_hierarchy_ids(
            session, project_entity
        )
        filtered_entities = self.filter_entities_by_selection(
            entities, selected_ids, parent_id_by_entity_id
        )
        entities_by_obj_id = {
            obj_id: []
            for obj_id in destination_object_type_ids
        }

        self.log.debug("Filtering Task entities.")
        task_entities_by_parent_id = collections.defaultdict(list)
        non_task_entities = []
        non_task_entity_ids = []
        for entity in entities:
            if entity.entity_type.lower() != "task":
                non_task_entities.append(entity)
                non_task_entity_ids.append(entity["id"])
                continue

            parent_id = entity["parent_id"]
            if parent_id in entities_by_id:
                task_entities_by_parent_id[parent_id].append(entity)

        task_attr_id_by_keys, hier_attrs = self.task_attributes(session)

        self.log.debug("Getting Custom attribute values from tasks' parents.")
        hier_values_by_entity_id = self.get_hier_values(
            session,
            hier_attrs,
            non_task_entity_ids
        )

        self.log.debug("Setting parents' values to task.")
        task_missing_keys = self.set_task_attr_values(
            session,
            task_entities_by_parent_id,
            hier_values_by_entity_id,
            task_attr_id_by_keys
        )

        self.log.debug("Setting values to entities themselves.")
        missing_keys_by_object_name = self.push_values_to_entities(
            session,
            non_task_entities,
            hier_values_by_entity_id
        )


    def all_hierarchy_ids(self, session, project_entity):
        parent_id_by_entity_id = {}

        hierarchy_entities = session.query(
            self.hierarchy_entities_query.format(project_entity["id"])
        )
        for hierarchy_entity in hierarchy_entities:
            entity_id = hierarchy_entity["id"]
            parent_id = hierarchy_entity["parent_id"]
            parent_id_by_entity_id[entity_id] = parent_id
        return parent_id_by_entity_id

    def filter_entities_by_selection(
        self, entities, selected_ids, parent_id_by_entity_id
    ):
        filtered_entities = []
        for entity in entities:
            entity_id = entity["id"]
            if entity_id in selected_ids:
                filtered_entities.append(entity)
                continue

            parent_id = entity["parent_id"]
            while True:
                if parent_id in selected_ids:
                    filtered_entities.append(entity)
                    break

                parent_id = parent_id_by_entity_id.get(parent_id)
                if parent_id is None:
                    break

        return filtered_entities

    def get_hier_values(self, session, hier_attrs, focus_entity_ids):
        joined_entity_ids = self.join_keys(focus_entity_ids)
        hier_attr_ids = self.join_keys(
            tuple(hier_attr["id"] for hier_attr in hier_attrs)
        )
        hier_attrs_key_by_id = {
            hier_attr["id"]: hier_attr["key"]
            for hier_attr in hier_attrs
        }
        call_expr = [{
            "action": "query",
            "expression": self.cust_attr_value_query.format(
                joined_entity_ids, hier_attr_ids
            )
        }]
        if hasattr(session, "call"):
            [values] = session.call(call_expr)
        else:
            [values] = session._call(call_expr)

        values_per_entity_id = {}
        for item in values["data"]:
            entity_id = item["entity_id"]
            key = hier_attrs_key_by_id[item["configuration_id"]]

            if entity_id not in values_per_entity_id:
                values_per_entity_id[entity_id] = {}
            value = item["value"]
            if value is not None:
                values_per_entity_id[entity_id][key] = value

        output = {}
        for entity_id in focus_entity_ids:
            value = values_per_entity_id.get(entity_id)
            if value:
                output[entity_id] = value

        return output

    def set_task_attr_values(
        self,
        session,
        task_entities_by_parent_id,
        hier_values_by_entity_id,
        task_attr_id_by_keys
    ):
        missing_keys = set()
        for parent_id, values in hier_values_by_entity_id.items():
            task_entities = task_entities_by_parent_id[parent_id]
            for hier_key, value in values.items():
                key = self.custom_attribute_mapping[hier_key]
                if key not in task_attr_id_by_keys:
                    missing_keys.add(key)
                    continue

                for task_entity in task_entities:
                    _entity_key = collections.OrderedDict({
                        "configuration_id": task_attr_id_by_keys[key],
                        "entity_id": task_entity["id"]
                    })

                    session.recorded_operations.push(
                        ftrack_api.operation.UpdateEntityOperation(
                            "ContextCustomAttributeValue",
                            _entity_key,
                            "value",
                            ftrack_api.symbol.NOT_SET,
                            value
                        )
                    )
        session.commit()

        return missing_keys

    def push_values_to_entities(
        self,
        session,
        non_task_entities,
        hier_values_by_entity_id
    ):
        object_types = session.query(
            "ObjectType where name in ({})".format(
                self.join_keys(self.pushing_entity_types)
            )
        ).all()
        object_type_names_by_id = {
            object_type["id"]: object_type["name"]
            for object_type in object_types
        }
        joined_keys = self.join_keys(
             self.custom_attribute_mapping.values()
        )
        attribute_entities = session.query(
            self.cust_attrs_query.format(joined_keys)
        ).all()

        attrs_by_obj_id = {}
        for attr in attribute_entities:
            if attr["is_hierarchical"]:
                continue

            obj_id = attr["object_type_id"]
            if obj_id not in object_type_names_by_id:
                continue

            if obj_id not in attrs_by_obj_id:
                attrs_by_obj_id[obj_id] = {}

            attr_key = attr["key"]
            attrs_by_obj_id[obj_id][attr_key] = attr["id"]

        entities_by_obj_id = collections.defaultdict(list)
        for entity in non_task_entities:
            entities_by_obj_id[entity["object_type_id"]].append(entity)

        missing_keys_by_object_id = collections.defaultdict(set)
        for obj_type_id, attr_keys in attrs_by_obj_id.items():
            entities = entities_by_obj_id.get(obj_type_id)
            if not entities:
                continue

            for entity in entities:
                values = hier_values_by_entity_id.get(entity["id"])
                if not values:
                    continue

                for hier_key, value in values.items():
                    key = self.custom_attribute_mapping[hier_key]
                    if key not in attr_keys:
                        missing_keys_by_object_id[obj_type_id].add(key)
                        continue

                    _entity_key = collections.OrderedDict({
                        "configuration_id": attr_keys[key],
                        "entity_id": entity["id"]
                    })

                    session.recorded_operations.push(
                        ftrack_api.operation.UpdateEntityOperation(
                            "ContextCustomAttributeValue",
                            _entity_key,
                            "value",
                            ftrack_api.symbol.NOT_SET,
                            value
                        )
                    )
        session.commit()

        missing_keys_by_object_name = {}
        for obj_id, missing_keys in missing_keys_by_object_id.items():
            obj_name = object_type_names_by_id[obj_id]
            missing_keys_by_object_name[obj_name] = missing_keys

        return missing_keys_by_object_name


def register(session, plugins_presets={}):
    PushFrameValuesToTaskAction(session, plugins_presets).register()
