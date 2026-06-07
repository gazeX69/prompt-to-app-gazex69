from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .capabilities import ContractCapability, infer_capability, normalize_capability
from .models import (
    ContractDescriptor,
    FeatureContractContext,
    FeatureContractResult,
    FeatureManifest,
)

FeatureContractCallable = Callable[[FeatureContractContext], Awaitable[FeatureContractResult]]


@dataclass(frozen=True)
class RegisteredFeatureContract:
    contract_id: str
    capability: ContractCapability
    handler: FeatureContractCallable | None = None


class FeatureContractRegistry:
    def __init__(self) -> None:
        self._contracts: dict[str, RegisteredFeatureContract] = {}
        self._descriptors: dict[str, ContractDescriptor] = {}
        self._capability_index: dict[ContractCapability, list[str]] = {}

    def register(
        self,
        contract_id: str,
        capability: str | ContractCapability,
        handler: FeatureContractCallable | None = None,
        description: str = "",
    ) -> None:
        normalized_capability = normalize_capability(capability)
        descriptor = ContractDescriptor(
            contract_id=contract_id,
            capability=normalized_capability,
            description=description,
        )
        self._descriptors[contract_id] = descriptor
        if contract_id not in self._capability_index.get(normalized_capability, []):
            self._capability_index.setdefault(normalized_capability, []).append(contract_id)
        if handler is not None:
            self._contracts[contract_id] = RegisteredFeatureContract(
                contract_id=contract_id,
                capability=normalized_capability,
                handler=handler,
            )

    def list_contracts(self) -> list[RegisteredFeatureContract]:
        return list(self._contracts.values())

    def list_descriptors(self) -> list[ContractDescriptor]:
        return list(self._descriptors.values())

    def get_contract(self, contract_id: str) -> RegisteredFeatureContract | None:
        return self._contracts.get(contract_id)

    def get_descriptor(self, contract_id: str) -> ContractDescriptor | None:
        return self._descriptors.get(contract_id)

    def capabilities_for_manifest(self, manifest: FeatureManifest | None) -> list[ContractCapability]:
        if manifest is None:
            return []
        capabilities: list[ContractCapability] = []
        seen: set[ContractCapability] = set()
        for feature in manifest.features:
            capability = infer_capability(feature)
            if capability == ContractCapability.UNKNOWN or capability in seen:
                continue
            capabilities.append(capability)
            seen.add(capability)
        return capabilities

    def select_contracts(self, manifest: FeatureManifest | None) -> list[ContractDescriptor]:
        if manifest is None:
            return self.list_descriptors()

        selected: list[ContractDescriptor] = []
        seen: set[str] = set()
        for capability in self.capabilities_for_manifest(manifest):
            for contract_id in self._capability_index.get(capability, []):
                if contract_id in seen:
                    continue
                descriptor = self._descriptors.get(contract_id)
                if descriptor is None:
                    continue
                selected.append(descriptor)
                seen.add(contract_id)
        return selected


default_registry = FeatureContractRegistry()
default_registry.register("entity_create", ContractCapability.CREATE_ENTITY, description="Future generic entity creation contract")
default_registry.register("entity_update", ContractCapability.UPDATE_ENTITY, description="Future generic entity update contract")
default_registry.register("entity_delete", ContractCapability.DELETE_ENTITY, description="Future generic entity deletion contract")
default_registry.register("entity_persist", ContractCapability.PERSIST_ENTITY, description="Future generic persistence contract")
default_registry.register("entity_search", ContractCapability.SEARCH_ENTITY, description="Future generic search contract")
default_registry.register("entity_filter", ContractCapability.FILTER_ENTITY, description="Future generic filter contract")
default_registry.register("user_auth", ContractCapability.AUTHENTICATE_USER, description="Future generic authentication contract")
default_registry.register("file_upload", ContractCapability.UPLOAD_FILE, description="Future generic upload contract")
default_registry.register("file_download", ContractCapability.DOWNLOAD_FILE, description="Future generic download contract")
default_registry.register("checkout_flow", ContractCapability.CHECKOUT, description="Future generic checkout contract")
default_registry.register("report_view", ContractCapability.VIEW_REPORT, description="Future generic reporting contract")
