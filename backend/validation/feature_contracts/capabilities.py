from enum import Enum

from .models import FeatureDescriptor


class ContractCapability(str, Enum):
    CREATE_ENTITY = "CREATE_ENTITY"
    UPDATE_ENTITY = "UPDATE_ENTITY"
    DELETE_ENTITY = "DELETE_ENTITY"
    PERSIST_ENTITY = "PERSIST_ENTITY"
    SEARCH_ENTITY = "SEARCH_ENTITY"
    FILTER_ENTITY = "FILTER_ENTITY"
    AUTHENTICATE_USER = "AUTHENTICATE_USER"
    UPLOAD_FILE = "UPLOAD_FILE"
    DOWNLOAD_FILE = "DOWNLOAD_FILE"
    CHECKOUT = "CHECKOUT"
    VIEW_REPORT = "VIEW_REPORT"
    UNKNOWN = "UNKNOWN"


ACTION_CAPABILITIES: dict[str, ContractCapability] = {
    "create": ContractCapability.CREATE_ENTITY,
    "add": ContractCapability.CREATE_ENTITY,
    "new": ContractCapability.CREATE_ENTITY,
    "edit": ContractCapability.UPDATE_ENTITY,
    "update": ContractCapability.UPDATE_ENTITY,
    "modify": ContractCapability.UPDATE_ENTITY,
    "change": ContractCapability.UPDATE_ENTITY,
    "adjust": ContractCapability.UPDATE_ENTITY,
    "delete": ContractCapability.DELETE_ENTITY,
    "remove": ContractCapability.DELETE_ENTITY,
    "clear": ContractCapability.DELETE_ENTITY,
    "persist": ContractCapability.PERSIST_ENTITY,
    "save": ContractCapability.PERSIST_ENTITY,
    "search": ContractCapability.SEARCH_ENTITY,
    "filter": ContractCapability.FILTER_ENTITY,
    "login": ContractCapability.AUTHENTICATE_USER,
    "auth": ContractCapability.AUTHENTICATE_USER,
    "upload": ContractCapability.UPLOAD_FILE,
    "download": ContractCapability.DOWNLOAD_FILE,
    "checkout": ContractCapability.CHECKOUT,
    "view": ContractCapability.VIEW_REPORT,
}

CATEGORY_CAPABILITIES: dict[str, ContractCapability] = {
    "create": ContractCapability.CREATE_ENTITY,
    "update": ContractCapability.UPDATE_ENTITY,
    "delete": ContractCapability.DELETE_ENTITY,
    "persist": ContractCapability.PERSIST_ENTITY,
    "search": ContractCapability.SEARCH_ENTITY,
    "filter": ContractCapability.FILTER_ENTITY,
    "auth": ContractCapability.AUTHENTICATE_USER,
    "file": ContractCapability.UPLOAD_FILE,
    "commerce": ContractCapability.CHECKOUT,
    "reporting": ContractCapability.VIEW_REPORT,
}

TECHNICAL_FEATURE_IDS = {
    "create_file",
    "replace_file",
    "append_file",
    "append_to_file",
    "insert_import",
    "replace_block",
    "modify_json_key",
}


def normalize_capability(capability: str | ContractCapability) -> ContractCapability:
    if isinstance(capability, ContractCapability):
        return capability
    raw = str(capability).strip()
    if not raw:
        return ContractCapability.UNKNOWN
    upper = raw.upper()
    if upper in ContractCapability.__members__:
        return ContractCapability[upper]
    for item in ContractCapability:
        if item.value == upper:
            return item
    return ContractCapability.UNKNOWN


def infer_capability(feature: FeatureDescriptor) -> ContractCapability:
    feature_id = (feature.id or "").strip().lower()
    if feature_id in TECHNICAL_FEATURE_IDS:
        return ContractCapability.UNKNOWN
    first_token = feature_id.split("_", 1)[0] if feature_id else ""
    if first_token in ACTION_CAPABILITIES:
        return ACTION_CAPABILITIES[first_token]
    category = (feature.category or "").strip().lower()
    return CATEGORY_CAPABILITIES.get(category, ContractCapability.UNKNOWN)
