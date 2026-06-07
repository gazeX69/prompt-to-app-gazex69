import logging
import time

from .actions import build_action_plan
from .browser import FeatureBrowserAdapter
from .models import FeatureContractContext, FeatureContractFailure, FeatureContractResult
from .registry import FeatureContractRegistry, default_registry

logger = logging.getLogger(__name__)


class FeatureContractRunner:
    def __init__(
        self,
        registry: FeatureContractRegistry | None = None,
        browser: FeatureBrowserAdapter | None = None,
    ) -> None:
        self.registry = registry or default_registry
        self.browser = browser or FeatureBrowserAdapter()

    async def run(self, context: FeatureContractContext) -> FeatureContractResult:
        started = time.perf_counter()
        selected_descriptors = self.registry.select_contracts(context.feature_manifest)
        selected_contract_ids = [contract.contract_id for contract in selected_descriptors]
        action_plans = [build_action_plan(contract) for contract in selected_descriptors]
        executable_contract_ids = set(selected_contract_ids) if context.feature_manifest else None
        contracts = [
            contract
            for contract in self.registry.list_contracts()
            if executable_contract_ids is None or contract.contract_id in executable_contract_ids
        ]
        executed: list[str] = []
        failures: list[FeatureContractFailure] = []
        feature_ids = [feature.id for feature in context.feature_manifest.features] if context.feature_manifest else []

        logger.info(
            "[FeatureContract] starting project_id=%s run_id=%s app_type=%s domain=%s features=%s selected_contracts=%s action_plans=%s executable_contracts=%s",
            context.project_id,
            context.run_id,
            context.app_type,
            context.domain,
            feature_ids,
            selected_contract_ids,
            [len(plan.actions) for plan in action_plans],
            len(contracts),
        )

        for contract in contracts:
            executed.append(contract.contract_id)
            try:
                result = await contract.handler(context)
            except Exception as exc:
                failures.append(
                    FeatureContractFailure(
                        contract_id=contract.contract_id,
                        message=str(exc),
                        detail={"capability": contract.capability},
                    )
                )
                continue

            if not result.success:
                failures.extend(result.failures)

        duration_ms = int((time.perf_counter() - started) * 1000)
        return FeatureContractResult(
            success=not failures,
            contracts_executed=executed,
            selected_contracts=selected_contract_ids,
            action_plans=action_plans,
            failures=failures,
            duration_ms=duration_ms,
        )


async def run_feature_contracts(context: FeatureContractContext) -> FeatureContractResult:
    return await FeatureContractRunner().run(context)
