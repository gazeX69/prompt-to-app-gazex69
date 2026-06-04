import re
from backend.brain.schemas import ComplexityLevel, PlanSignature


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]


def _has_word(prompt_lower: str, word: str) -> bool:
    return bool(re.search(rf'\b{re.escape(word)}\b', prompt_lower))


def _get_broad_match_type(prompt: str) -> str | None:
    prompt_lower = prompt.lower()
    prompt_clean = re.sub(r'[^a-z0-9\s]', ' ', prompt_lower)
    words = prompt_clean.split()
    
    # Mapping of target keys to app types
    mappings = {
        "marketplace": "marketplace",
        "ecommerce": "marketplace",
        "socialmedia": "social media",
        "dashboard": "dashboard",
        "inventory": "inventory",
        "inventori": "inventory",
        "recruitment": "recruitment",
        "rekrutmen": "recruitment",
        "finance": "finance",
        "booking": "booking",
    }
    
    # Direct whole-word and phrase checks
    if any(_has_word(prompt_lower, k) for k in ["marketplace", "toko online", "online shop", "olshop", "marketpce", "marketplac", "marketpleis"]):
        return "marketplace"
    if any(_has_word(prompt_lower, k) for k in ["e-commerce", "ecommerce", "e-comerce", "ecomerce"]):
        return "marketplace"
    if any(_has_word(prompt_lower, k) for k in ["saas", "sas", "sasa"]):
        return "saas"
    if any(_has_word(prompt_lower, k) for k in ["lms", "lsm"]):
        return "lms"
    if any(_has_word(prompt_lower, k) for k in ["erp", "epr"]):
        return "erp"
    if any(_has_word(prompt_lower, k) for k in ["crm", "cmr"]):
        return "crm"
    if any(_has_word(prompt_lower, k) for k in ["social media", "sosial media"]):
        return "social media"
    if any(_has_word(prompt_lower, k) for k in ["dashboard", "admin dashboard", "dashboard admin"]):
        return "dashboard"
    if any(_has_word(prompt_lower, k) for k in ["crud", "crud besar", "crud kompleks", "complex crud", "multi-entity crud"]):
        return "crud_app"
    if any(_has_word(prompt_lower, k) for k in ["inventory", "inventori", "stok", "stock", "gudang"]):
        return "inventory"
    if any(_has_word(prompt_lower, k) for k in ["recruitment", "rekrutmen", "lowongan"]):
        return "recruitment"
    if any(_has_word(prompt_lower, k) for k in ["finance", "keuangan", "accounting", "akuntansi"]):
        return "finance"
    if any(_has_word(prompt_lower, k) for k in ["booking", "reservasi", "appointment"]):
        return "booking"
    if any(_has_word(prompt_lower, k) for k in ["pos", "point of sale", "kasir"]):
        return "pos"
    if _has_word(prompt_lower, "cms"):
        return "cms"
        
    # Levenshtein distance check for longer words only to prevent false positives
    for word in words:
        if len(word) < 5:
            continue
        for target, app_type in mappings.items():
            if abs(len(word) - len(target)) > 2:
                continue
            max_dist = 2 if len(target) < 8 else 3
            if _levenshtein_distance(word, target) <= max_dist:
                return app_type
                
    return None


CRUD_TERMS = ["crud", "create read update delete"]
CRUD_ENTITIES = [
    "todo",
    "task",
    "produk",
    "product",
    "barang",
    "item",
    "user",
    "customer",
    "employee",
    "student",
    "book",
    "order",
    "transaction",
    "transaksi",
]
CRUD_STORAGE_TERMS = [
    "local storage",
    "localstorage",
    "sql",
    "mysql",
    "postgres",
    "sqlite",
    "database",
    "db",
    "json",
    "backend",
    "api",
]


def _has_crud(text: str) -> bool:
    return _contains_any(text, CRUD_TERMS)


def _has_crud_entity(text: str) -> bool:
    return _contains_any(text, CRUD_ENTITIES)


def _has_crud_storage(text: str) -> bool:
    return _contains_any(text, CRUD_STORAGE_TERMS)


def build_plan_signature(prompt: str) -> PlanSignature:
    text = prompt.strip().lower()
    intent = "build_app" if _contains_any(text, ["buat", "build", "create", "make", "aplikasi", "app", "crud"]) else "unknown"

    domain = "general"
    app_type = "app"
    complexity = ComplexityLevel.MEDIUM
    feature_keywords: list[str] = []
    required_capabilities: list[str] = ["state_management"]

    broad_type = _get_broad_match_type(prompt)

    if _contains_any(text, ["hello world", "halo dunia"]):
        domain = "utility"
        app_type = "hello_world"
        complexity = ComplexityLevel.LOW
        feature_keywords = ["hello_world"]
        required_capabilities = ["static_rendering"]
    elif broad_type == "marketplace":
        domain = "marketplace"
        app_type = "marketplace"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["products", "cart", "checkout", "admin"]
        required_capabilities = ["crud", "state_management", "product_catalog", "cart", "checkout_simulation"]
    elif broad_type == "inventory":
        domain = "inventory"
        app_type = "inventory"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["items", "stock", "crud", "reporting"]
        required_capabilities = ["crud", "state_management", "data_persistence", "reporting"]
    elif broad_type == "recruitment":
        domain = "recruitment"
        app_type = "recruitment"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["jobs", "candidates", "pipeline", "admin"]
        required_capabilities = ["crud", "state_management", "data_persistence", "roles", "workflow"]
    elif broad_type == "finance":
        domain = "finance"
        app_type = "finance"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["transactions", "reports", "categories", "dashboard"]
        required_capabilities = ["crud", "state_management", "data_persistence", "reporting"]
    elif broad_type == "booking":
        domain = "booking"
        app_type = "booking"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["calendar", "availability", "booking", "admin"]
        required_capabilities = ["crud", "state_management", "data_persistence", "calendar"]
    elif broad_type == "pos":
        domain = "pos"
        app_type = "pos"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["products", "sales", "cart", "receipt"]
        required_capabilities = ["crud", "state_management", "data_persistence", "cart", "reporting"]
    elif broad_type == "cms":
        domain = "content"
        app_type = "cms"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["pages", "posts", "editor", "admin"]
        required_capabilities = ["crud", "state_management", "data_persistence", "admin_panel"]
    elif broad_type == "lms":
        domain = "education"
        app_type = "lms"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["courses", "lessons", "students", "progress", "admin"]
        required_capabilities = ["crud", "state_management", "data_persistence", "roles", "progress_tracking"]
    elif broad_type == "saas":
        domain = "saas"
        app_type = "saas"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["subscription", "auth", "dashboard", "billing"]
        required_capabilities = ["crud", "state_management", "data_persistence", "authentication", "billing_simulation"]
    elif broad_type == "social media":
        domain = "social"
        app_type = "social media"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["profiles", "posts", "feed", "comments"]
        required_capabilities = ["crud", "state_management", "data_persistence", "realtime"]
    elif broad_type == "dashboard":
        domain = "dashboard"
        app_type = "dashboard"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["dashboard", "charts", "auth", "database", "admin"]
        required_capabilities = ["state_management", "data_persistence", "reporting"]
    elif broad_type == "crud_app":
        domain = "crud"
        app_type = "crud_app"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["crud", "entities", "database"]
        required_capabilities = ["crud", "state_management", "data_persistence"]
    elif _contains_any(text, ["login", "auth", "authentication", "register"]):
        domain = "auth"
        app_type = "auth_app"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["auth", "login", "session"]
        required_capabilities = ["state_management", "data_persistence", "backend_api", "authentication"]
    elif _contains_any(text, ["database", "db", "sql", "mysql", "postgres", "sqlite"]):
        domain = "data"
        app_type = "data_app"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["database", "persistence"]
        required_capabilities = ["state_management", "data_persistence"]
    elif _contains_any(text, ["todo", "to-do", "task list"]):
        domain = "utility"
        app_type = "todo"
        complexity = ComplexityLevel.LOW
        feature_keywords = ["tasks"]
        required_capabilities = ["crud", "state_management"]
    elif _contains_any(text, ["counter", "penghitung"]):
        domain = "utility"
        app_type = "counter"
        complexity = ComplexityLevel.LOW
        feature_keywords = ["counter"]
        required_capabilities = ["state_management"]
    elif _contains_any(text, ["calculator", "kalkulator"]):
        domain = "utility"
        app_type = "calculator"
        complexity = ComplexityLevel.LOW
        feature_keywords = ["calculator"]
        required_capabilities = ["state_management"]

    if _contains_any(text, ["admin"]) and "admin" not in feature_keywords:
        feature_keywords.append("admin")
    if _has_crud(text) and app_type == "app":
        domain = "crud"
        app_type = "crud_app"
        complexity = ComplexityLevel.MEDIUM
        feature_keywords.extend(["crud"])
        required_capabilities.extend(["crud", "state_management"])
        if _has_crud_storage(text):
            required_capabilities.append("data_persistence")
    if _has_crud(text) and "crud" not in required_capabilities:
        required_capabilities.append("crud")
    if _contains_any(text, ["database", "db", "persist", "simpan data"]) and "data_persistence" not in required_capabilities:
        required_capabilities.append("data_persistence")

    # Short / Vague prompt skeptic heuristic
    words = text.split()
    is_simple_known = app_type in ["hello_world", "todo", "counter", "calculator"]
    if intent == "build_app" and not is_simple_known and app_type == "app":
        if len(words) <= 5 or len(text) <= 45:
            domain = "general"
            app_type = "crud_app"
            complexity = ComplexityLevel.HIGH
            feature_keywords.extend(["crud", "database"])
            required_capabilities.extend(["crud", "state_management", "data_persistence"])

    return PlanSignature(
        domain=domain,
        intent=intent,
        app_type=app_type,
        complexity=complexity,
        feature_keywords=_unique(feature_keywords),
        required_capabilities=_unique(required_capabilities),
    )

