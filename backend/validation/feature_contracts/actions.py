from dataclasses import asdict, dataclass, field
from typing import Any

from .capabilities import ContractCapability
from .models import ContractDescriptor


@dataclass(frozen=True)
class BrowserAction:
    action_type: str
    target: str | None = None
    value: Any | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BrowserActionResult:
    action: BrowserAction
    success: bool
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "success": self.success,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass
class ActionPlan:
    contract_id: str
    capability: ContractCapability
    actions: list[BrowserAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "capability": self.capability.value,
            "actions": [action.to_dict() for action in self.actions],
        }


ACTION_TEMPLATES: dict[ContractCapability, list[tuple[str, str]]] = {
    ContractCapability.CREATE_ENTITY: [
        ("locate_create_control", "Find a generic create control"),
        ("open_creator", "Open the generic creation surface"),
        ("submit_new_entity", "Submit a representative new entity"),
        ("verify_entity_created", "Verify the entity appears after creation"),
    ],
    ContractCapability.UPDATE_ENTITY: [
        ("locate_entity", "Find a representative entity"),
        ("open_editor", "Open the generic editing surface"),
        ("modify_value", "Modify a representative value"),
        ("save_changes", "Save the edited entity"),
        ("verify_change", "Verify the changed value is visible"),
    ],
    ContractCapability.DELETE_ENTITY: [
        ("locate_entity", "Find a representative entity"),
        ("trigger_delete", "Trigger generic delete behavior"),
        ("confirm_delete", "Confirm deletion when confirmation exists"),
        ("verify_deleted", "Verify the entity no longer appears"),
    ],
    ContractCapability.PERSIST_ENTITY: [
        ("capture_state", "Capture visible entity state"),
        ("reload_preview", "Reload the preview"),
        ("verify_state_persisted", "Verify entity state remains after reload"),
    ],
    ContractCapability.SEARCH_ENTITY: [
        ("locate_search", "Find a search control"),
        ("enter_query", "Enter a representative query"),
        ("verify_filtered_results", "Verify results match the query"),
    ],
    ContractCapability.FILTER_ENTITY: [
        ("locate_filter", "Find a filter control"),
        ("apply_filter", "Apply a representative filter"),
        ("verify_filtered_results", "Verify filtered results"),
    ],
    ContractCapability.AUTHENTICATE_USER: [
        ("locate_login", "Find login controls"),
        ("submit_credentials", "Submit representative credentials"),
        ("verify_authenticated_state", "Verify authenticated state is visible"),
    ],
    ContractCapability.UPLOAD_FILE: [
        ("locate_upload", "Find an upload control"),
        ("select_file", "Select a representative file"),
        ("verify_upload", "Verify upload result is visible"),
    ],
    ContractCapability.DOWNLOAD_FILE: [
        ("locate_download", "Find a download control"),
        ("trigger_download", "Trigger a representative download"),
        ("verify_download_started", "Verify download starts"),
    ],
    ContractCapability.CHECKOUT: [
        ("locate_checkout", "Find checkout entrypoint"),
        ("start_checkout", "Start generic checkout flow"),
        ("verify_checkout_state", "Verify checkout state changes"),
    ],
    ContractCapability.VIEW_REPORT: [
        ("locate_report", "Find reporting surface"),
        ("open_report", "Open a representative report"),
        ("verify_report_visible", "Verify report content is visible"),
    ],
}


def build_action_plan(contract: ContractDescriptor) -> ActionPlan:
    templates = ACTION_TEMPLATES.get(contract.capability, [])
    return ActionPlan(
        contract_id=contract.contract_id,
        capability=contract.capability,
        actions=[
            BrowserAction(action_type=action_type, description=description)
            for action_type, description in templates
        ],
    )
