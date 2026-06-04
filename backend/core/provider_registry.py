import os
import logging
from typing import Dict, List, Optional
from uuid import uuid4
from backend.brain.memory_store import load_providers, write_providers
from backend.core.providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

class ProviderRegistry:
    _instance: Optional["ProviderRegistry"] = None

    def __init__(self):
        self._ensure_default_instances()

    @classmethod
    def get_instance(cls) -> "ProviderRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_default_instances(self):
        """Initializes default provider instances from env vars if providers.json is empty."""
        try:
            instances = load_providers()
            if not instances:
                # Pre-populate defaults based on environment keys
                instances = []
                priority = 1
                
                # Qwen
                has_qwen = bool(os.getenv("DASHSCOPE_API_KEY"))
                instances.append({
                    "id": "default_qwen",
                    "name": "Qwen Primary" if has_qwen else "Qwen (Unconfigured)",
                    "provider_type": "qwen",
                    "api_key": os.getenv("DASHSCOPE_API_KEY") or "",
                    "base_url": os.getenv("QWEN_BASE_URL") or "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen-plus",
                    "priority": priority,
                    "is_enabled": True,
                    "is_default": True
                })
                priority += 1
                
                # OpenAI
                has_openai = bool(os.getenv("OPENAI_API_KEY"))
                instances.append({
                    "id": "default_openai",
                    "name": "OpenAI Primary" if has_openai else "OpenAI (Unconfigured)",
                    "provider_type": "openai",
                    "api_key": os.getenv("OPENAI_API_KEY") or "",
                    "base_url": "",
                    "model": "gpt-4o",
                    "priority": priority,
                    "is_enabled": has_openai,
                    "is_default": False
                })
                priority += 1
                
                # Gemini
                has_gemini = bool(os.getenv("GEMINI_API_KEY"))
                instances.append({
                    "id": "default_gemini",
                    "name": "Gemini Primary" if has_gemini else "Gemini (Unconfigured)",
                    "provider_type": "gemini",
                    "api_key": os.getenv("GEMINI_API_KEY") or "",
                    "base_url": "",
                    "model": "gemini-1.5-flash",
                    "priority": priority,
                    "is_enabled": has_gemini,
                    "is_default": False
                })
                priority += 1

                # Anthropic
                has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
                instances.append({
                    "id": "default_anthropic",
                    "name": "Anthropic Primary" if has_anthropic else "Anthropic (Unconfigured)",
                    "provider_type": "anthropic",
                    "api_key": os.getenv("ANTHROPIC_API_KEY") or "",
                    "base_url": "",
                    "model": "claude-3-5-sonnet-20241022",
                    "priority": priority,
                    "is_enabled": has_anthropic,
                    "is_default": False
                })
                priority += 1
                
                # Local LLM
                instances.append({
                    "id": "default_local",
                    "name": "Local LLM",
                    "provider_type": "local",
                    "api_key": "",
                    "base_url": os.getenv("LOCAL_LLM_URL") or "http://localhost:11434/v1",
                    "model": os.getenv("LOCAL_LLM_MODEL") or "llama3",
                    "priority": priority,
                    "is_enabled": False,
                    "is_default": False
                })
                
                write_providers(instances)
                logger.info("Initialized default provider instances in providers.json")
        except Exception as e:
            logger.exception("Failed to ensure default provider instances: %s", e)

    def list_instances(self) -> List[Dict[str, any]]:
        return load_providers()

    def get_instance_by_id(self, id: str) -> Optional[Dict[str, any]]:
        instances = self.list_instances()
        return next((inst for inst in instances if inst["id"] == id), None)

    def add_instance(self, data: Dict[str, any]) -> Dict[str, any]:
        instances = self.list_instances()
        new_inst = {
            "id": f"agent_{uuid4().hex[:8]}",
            "name": data.get("name") or f"Agent {data.get('provider_type', 'unknown').upper()}",
            "provider_type": data.get("provider_type", "qwen"),
            "api_key": data.get("api_key") or "",
            "base_url": data.get("base_url") or "",
            "model": data.get("model") or "qwen-plus",
            "priority": int(data.get("priority") or 5),
            "is_enabled": bool(data.get("is_enabled", True)),
            "is_default": False
        }
        instances.append(new_inst)
        write_providers(instances)
        return new_inst

    def update_instance(self, id: str, data: Dict[str, any]) -> Dict[str, any]:
        instances = self.list_instances()
        updated = None
        for inst in instances:
            if inst["id"] == id:
                inst["name"] = data.get("name", inst["name"])
                inst["provider_type"] = data.get("provider_type", inst["provider_type"])
                if "api_key" in data:
                    inst["api_key"] = data["api_key"]
                inst["base_url"] = data.get("base_url", inst["base_url"])
                inst["model"] = data.get("model", inst["model"])
                inst["priority"] = int(data.get("priority", inst["priority"]))
                inst["is_enabled"] = bool(data.get("is_enabled", inst["is_enabled"]))
                updated = inst
                break
        if not updated:
            raise ValueError(f"Instance with ID {id} not found.")
        write_providers(instances)
        return updated

    def delete_instance(self, id: str):
        instances = self.list_instances()
        new_instances = [inst for inst in instances if inst["id"] != id]
        if len(new_instances) == len(instances):
            raise ValueError(f"Instance with ID {id} not found.")
        
        # If deleted default, pick another one as default
        was_default = any(inst["id"] == id and inst.get("is_default", False) for inst in instances)
        if was_default and new_instances:
            new_instances[0]["is_default"] = True
            
        write_providers(new_instances)

    def set_default_instance_id(self, id: str):
        instances = self.list_instances()
        found = False
        for inst in instances:
            if inst["id"] == id:
                inst["is_default"] = True
                found = True
            else:
                inst["is_default"] = False
        if not found:
            raise ValueError(f"Instance with ID {id} not found.")
        write_providers(instances)

    def get_default_instance_id(self) -> str:
        instances = self.list_instances()
        default_inst = next((inst for inst in instances if inst.get("is_default", False)), None)
        if default_inst:
            return default_inst["id"]
        if instances:
            return instances[0]["id"]
        return "default_qwen"

    def get_default_provider(self) -> BaseProvider:
        default_id = self.get_default_instance_id()
        inst = self.get_instance_by_id(default_id)
        if not inst:
            # Fallback Qwen
            from backend.core.providers import QwenProvider
            return QwenProvider()
            
        from backend.core.providers import (
            QwenProvider, OpenAIProvider, GeminiProvider, AnthropicProvider, LocalProvider
        )
        provider_type = inst["provider_type"]
        api_key = inst.get("api_key")
        base_url = inst.get("base_url")
        inst_model = inst.get("model")
        
        if provider_type == "qwen":
            return QwenProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
        elif provider_type == "openai":
            return OpenAIProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
        elif provider_type == "gemini":
            return GeminiProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
        elif provider_type == "anthropic":
            return AnthropicProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
        elif provider_type == "local":
            return LocalProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
            
        return QwenProvider()

    def complete_with_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = None,
        max_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> str:
        instances = self.list_instances()
        enabled_instances = [inst for inst in instances if inst.get("is_enabled", True)]
        enabled_instances.sort(key=lambda x: (x.get("priority", 99), x.get("id")))

        if not enabled_instances:
            raise ValueError("No AI provider instances are enabled/configured.")

        errors = []
        for inst in enabled_instances:
            inst_id = inst["id"]
            inst_name = inst["name"]
            provider_type = inst["provider_type"]
            # Enforce model compatibility when switching providers
            if model and model != "qwen-plus":
                is_compat = False
                if provider_type == "openai" and ("gpt" in model or "o1" in model):
                    is_compat = True
                elif provider_type == "qwen" and "qwen" in model:
                    is_compat = True
                elif provider_type == "gemini" and "gemini" in model:
                    is_compat = True
                elif provider_type == "anthropic" and ("claude" in model or "anthropic" in model):
                    is_compat = True
                elif provider_type == "local":
                    is_compat = True
                inst_model = model if is_compat else inst.get("model")
            else:
                inst_model = inst.get("model")


            import time
            from backend.services.telemetry_service import TelemetryService
            start_time = time.perf_counter()
            try:
                from backend.core.providers import (
                    QwenProvider, OpenAIProvider, GeminiProvider, AnthropicProvider, LocalProvider
                )
                provider_obj = None
                api_key = inst.get("api_key")
                base_url = inst.get("base_url")

                if provider_type == "qwen":
                    provider_obj = QwenProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
                elif provider_type == "openai":
                    provider_obj = OpenAIProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
                elif provider_type == "gemini":
                    provider_obj = GeminiProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
                elif provider_type == "anthropic":
                    provider_obj = AnthropicProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
                elif provider_type == "local":
                    provider_obj = LocalProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
                else:
                    raise ValueError(f"Unknown provider type: {provider_type}")

                if not provider_obj.is_available():
                    raise ValueError("Provider API key or configuration is missing/invalid")

                logger.info(f"Attempting completion with agent instance '{inst_name}' ({provider_type})")
                res = provider_obj.complete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=inst_model,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                prompt_tokens = getattr(provider_obj, "last_prompt_tokens", None)
                completion_tokens = getattr(provider_obj, "last_completion_tokens", None)
                
                TelemetryService.log_call(
                    provider_id=inst_id,
                    provider_name=inst_name,
                    provider_type=provider_type,
                    model=inst_model,
                    latency_ms=latency_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    status="success",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response=res
                )
                return res
            except Exception as e:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                TelemetryService.log_call(
                    provider_id=inst_id,
                    provider_name=inst_name,
                    provider_type=provider_type,
                    model=inst_model,
                    latency_ms=latency_ms,
                    prompt_tokens=None,
                    completion_tokens=None,
                    status="failed",
                    error_message=str(e),
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response=""
                )
                
                # Log failover event
                current_idx = enabled_instances.index(inst)
                if current_idx + 1 < len(enabled_instances):
                    next_inst = enabled_instances[current_idx + 1]
                    TelemetryService.log_failover(
                        failed_id=inst_id,
                        failed_name=inst_name,
                        failed_type=provider_type,
                        error_message=str(e),
                        next_id=next_inst["id"],
                        next_name=next_inst["name"],
                        next_type=next_inst["provider_type"]
                    )
                
                err_msg = f"Failed using agent '{inst_name}' ({provider_type}): {str(e)}"
                logger.warning(err_msg)
                errors.append(err_msg)
                
                try:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        from backend.sockets.manager import emit_terminal_line
                        loop.create_task(emit_terminal_line(f"[AutoSwitch] {err_msg}. Trying next agent...", "stderr"))
                except Exception:
                    pass


        raise ValueError(f"All AI provider instances failed. Errors: {'; '.join(errors)}")

# Helper shortcut functions
def get_provider(id: str) -> BaseProvider:
    # Legacy wrapper compatibility: maps type name or ID to instance object
    registry = ProviderRegistry.get_instance()
    inst = registry.get_instance_by_id(id)
    if not inst:
        # Check if matched by provider_type
        instances = registry.list_instances()
        inst = next((x for x in instances if x["provider_type"] == id), None)
        
    if not inst:
        from backend.core.providers import QwenProvider
        return QwenProvider()
        
    from backend.core.providers import (
        QwenProvider, OpenAIProvider, GeminiProvider, AnthropicProvider, LocalProvider
    )
    provider_type = inst["provider_type"]
    api_key = inst.get("api_key")
    base_url = inst.get("base_url")
    inst_model = inst.get("model")
    
    if provider_type == "qwen":
        return QwenProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
    elif provider_type == "openai":
        return OpenAIProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
    elif provider_type == "gemini":
        return GeminiProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
    elif provider_type == "anthropic":
        return AnthropicProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
    elif provider_type == "local":
        return LocalProvider(api_key=api_key, base_url=base_url, default_model=inst_model)
        
    return QwenProvider()

def get_default_provider() -> BaseProvider:
    return ProviderRegistry.get_instance().get_default_provider()

def list_providers() -> List[Dict[str, any]]:
    # Legacy list format compatibility
    instances = ProviderRegistry.get_instance().list_instances()
    default_id = ProviderRegistry.get_instance().get_default_instance_id()
    result = []
    for inst in instances:
        # Check availability
        try:
            prov = get_provider(inst["id"])
            avail = prov.is_available()
        except Exception:
            avail = False
            
        result.append({
            "name": inst["name"],
            "available": avail,
            "default_model": inst["model"],
            "is_default": inst["id"] == default_id,
            "provider_type": inst["provider_type"],
            "id": inst["id"],
            "priority": inst.get("priority", 5),
            "is_enabled": inst.get("is_enabled", True)
        })
    return result

def set_default_provider(id: str):
    ProviderRegistry.get_instance().set_default_instance_id(id)

