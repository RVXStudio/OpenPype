from openpype import OP4_TEST_ENABLED

from .operations_base import REMOVED_VALUE
if not OP4_TEST_ENABLED:
    from .mongo.operations import *
    OperationsSession = MongoOperationsSession

else:
    from .server.operations import *
    from .mongo.operations import (
        CURRENT_PROJECT_SCHEMA,
        CURRENT_PROJECT_CONFIG_SCHEMA,
        CURRENT_ASSET_DOC_SCHEMA,
        CURRENT_SUBSET_SCHEMA,
        CURRENT_VERSION_SCHEMA,
        CURRENT_HERO_VERSION_SCHEMA,
        CURRENT_REPRESENTATION_SCHEMA,
        CURRENT_WORKFILE_INFO_SCHEMA,
        CURRENT_THUMBNAIL_SCHEMA
    )
