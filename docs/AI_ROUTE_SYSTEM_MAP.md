# AI ROUTE SYSTEM MAP

## A. High Level Architecture

The AI Route Orchestration layer serves as the central nervous system for routing AI requests within the project. It abstracts away specific LLM providers and enables intelligent routing based on capabilities, health, and fallback mechanisms.

- **Provider Flow**: Providers are registered dynamically. When an AI capability is requested, the system queries the registry to find all providers that support the capability.
- **Routing Flow**: The router evaluates available providers, checking their current health status and user-defined preferences, before dispatching the request to the optimal provider.
- **Capability Resolution**: Requests specify *what* they need (e.g., `code-generation`, `fast-completion`, `vision`) rather than *who* should do it. The orchestration layer resolves this capability to a specific model.
- **Model Selection**: The system allows multi-model support, enabling fallback strategies if the primary model fails or times out.
- **Future Extensibility**: The architecture is designed to easily onboard local LLMs (e.g., Ollama, Llama.cpp) and other API providers without altering the core business logic.

---

## B. Core Components

### `provider.registry.ts`
Acts as the central directory for all available AI providers. It maintains the state of active providers, their supported capabilities, and their metadata.

### `ai-provider.interface.ts`
The strict contract that all AI provider adapters must implement. It ensures standardized methods for `generate`, `stream`, `healthCheck`, and `getCapabilities`.

### `capability.interface.ts`
Defines the taxonomy of AI capabilities (e.g., streaming, vision, function-calling, context-window limits). It is used to match a user's request requirements with a provider's strengths.

### `ai-router.service.ts`
The decision engine. It receives a capability request, queries the `provider.registry.ts`, evaluates provider health, and routes the request to the correct `ai-provider.interface.ts` implementation.

### Orchestration Module
Coordinates complex, multi-step AI tasks. If a task requires planning, generation, and validation, the orchestration module manages the state and intermediate context between router calls.

### Settings UI Integration
Hooks that allow the frontend to read from and write to the provider registry, enabling users to switch models, input API keys, and configure fallbacks in real-time.

### Fallback Mechanism
A built-in safety net in `ai-router.service.ts`. If a primary provider throws a 5xx error or times out, the router automatically attempts the request on the next available provider with matching capabilities.

### Provider Health Logic
A background polling or reactive mechanism that tracks the availability and latency of providers, updating their status in the registry.

### Mock Provider
A specialized `ai-provider.interface.ts` implementation used strictly for testing, offline development, or as a last-resort fallback to ensure the UI does not crash.

---

## C. Request Lifecycle

```text
+----------------+      +-----------------------+      +-------------------+
|  User Request  | ---> | Capability Detection  | ---> | Provider Matching |
| (Frontend/IDE) |      | (What do we need?)    |      | (Who can do it?)  |
+----------------+      +-----------------------+      +-------------------+
                                                                 |
                                                                 v
+----------------+      +-----------------------+      +-------------------+
|  UI Rendering  | <--- |   Response Adapter    | <--- |      Routing      |
| (Stream/Batch) |      | (Normalize output)    |      | (Execute & Retry) |
+----------------+      +-----------------------+      +-------------------+
```

---

## D. Error Surface Map

| Error Scenario | Location | Probable Cause | Impact | Debugging Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Provider Unavailable** | `ai-provider.interface.ts` | API outage, network drop | Request fails | Check health endpoint; trigger fallback |
| **Invalid Capability** | `ai-router.service.ts` | Requesting unsupported feature | Router rejection | Audit `capability.interface.ts` mapping |
| **Missing API Key** | `provider.registry.ts` | User didn't configure keys | Unauthorized | Prompt Settings UI Integration |
| **Timeout** | `ai-router.service.ts` | Slow model generation | Broken stream | Check Provider Health Logic; adjust timeout |
| **Malformed Response** | Response Adapter | Provider changed API format | Parse failure | Log raw output; update adapter contract |
| **Unsupported Streaming** | `ai-router.service.ts` | Requested stream on batch model | Connection hang | Fallback to batch processing mode |
| **Provider Mismatch** | `provider.registry.ts` | Hardcoded provider ID used | Routing bypassed | Enforce capability-based routing |

---

## E. Recovery Strategy

- **Fallback Provider**: If the primary model (e.g., `qwen-plus`) fails, the router seamlessly shifts to a secondary model with equivalent capabilities.
- **Retry Strategy**: Implement exponential backoff for transient errors (429 Too Many Requests, 502 Bad Gateway) before triggering a full fallback.
- **Graceful Degradation**: If advanced capabilities (like vision or massive context) fail, the system should gracefully degrade to simpler models and inform the user.
- **Mock Fallback**: In offline scenarios, the router falls back to the Mock Provider to simulate responses and prevent runtime panics.
- **Offline Handling**: Queues requests locally if network connectivity is lost, resuming when the connection is restored.

---

## F. Future Expansion

### Cara Menambah Provider Baru
1. Create a new class implementing `ai-provider.interface.ts`.
2. Define its capabilities using `capability.interface.ts`.
3. Register the class instance in `provider.registry.ts` on initialization.

### Cara Menambah Capability Baru
1. Add the capability enum/type to `capability.interface.ts`.
2. Update existing providers to explicitly declare support (or lack thereof) for the new capability.
3. Add routing logic in `ai-router.service.ts` to handle the new capability requirement.

### Cara Membuat Local LLM Adapter
1. Implement `ai-provider.interface.ts` with HTTP calls pointing to `localhost` (e.g., Ollama API).
2. Configure Provider Health Logic to silently fail without throwing global errors if the local server is down.

### Cara Membuat OpenAI-Compatible Adapter
1. Create a generic adapter that accepts a `baseURL` and `apiKey`.
2. Implement standard OpenAI REST endpoints within `ai-provider.interface.ts`.
3. Allow the Settings UI to dynamically instantiate multiple instances of this adapter for different compatible services.
