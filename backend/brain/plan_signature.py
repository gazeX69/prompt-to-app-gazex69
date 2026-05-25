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


def build_plan_signature(prompt: str) -> PlanSignature:
    text = prompt.strip().lower()
    intent = "build_app" if _contains_any(text, ["buat", "build", "create", "aplikasi", "app"]) else "unknown"

    domain = "general"
    app_type = "app"
    complexity = ComplexityLevel.MEDIUM
    feature_keywords: list[str] = []
    required_capabilities: list[str] = ["state_management"]

    if _contains_any(text, ["marketplace", "e-commerce", "ecommerce", "toko online", "online shop"]):
        domain = "marketplace"
        app_type = "marketplace"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["products", "cart", "checkout", "admin"]
        required_capabilities = ["crud", "state_management", "product_catalog", "cart", "checkout_simulation"]
    elif _contains_any(text, ["inventory", "inventori", "stok", "stock", "barang", "gudang"]):
        domain = "inventory"
        app_type = "inventory"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["items", "stock", "crud", "reporting"]
        required_capabilities = ["crud", "state_management", "data_persistence", "reporting"]
    elif _contains_any(text, ["lms", "learning management", "kursus", "course", "kelas online"]):
        domain = "education"
        app_type = "lms"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["courses", "lessons", "students", "progress", "admin"]
        required_capabilities = ["crud", "state_management", "data_persistence", "roles", "progress_tracking"]
    elif _contains_any(text, ["recruitment", "rekrutmen", "lowongan", "applicant", "ats"]):
        domain = "recruitment"
        app_type = "recruitment"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["jobs", "candidates", "pipeline", "admin"]
        required_capabilities = ["crud", "state_management", "data_persistence", "roles", "workflow"]
    elif _contains_any(text, ["finance", "keuangan", "accounting", "akuntansi", "invoice", "budget"]):
        domain = "finance"
        app_type = "finance"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["transactions", "reports", "categories", "dashboard"]
        required_capabilities = ["crud", "state_management", "data_persistence", "reporting"]
    elif _contains_any(text, ["crm", "customer relationship"]):
        domain = "crm"
        app_type = "crm"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["customers", "pipeline", "tasks", "reporting"]
        required_capabilities = ["crud", "state_management", "data_persistence", "reporting"]
    elif _contains_any(text, ["erp"]):
        domain = "erp"
        app_type = "erp"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["modules", "roles", "workflow", "reporting"]
        required_capabilities = ["crud", "state_management", "data_persistence", "roles", "reporting"]
    elif _contains_any(text, ["pos", "point of sale", "kasir"]):
        domain = "pos"
        app_type = "pos"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["products", "sales", "cart", "receipt"]
        required_capabilities = ["crud", "state_management", "data_persistence", "cart", "reporting"]
    elif _contains_any(text, ["booking", "reservasi", "appointment"]):
        domain = "booking"
        app_type = "booking"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["calendar", "availability", "booking", "admin"]
        required_capabilities = ["crud", "state_management", "data_persistence", "calendar"]
    elif _contains_any(text, ["social media", "sosial media", "jejaring sosial"]):
        domain = "social"
        app_type = "social media"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["profiles", "posts", "feed", "comments"]
        required_capabilities = ["crud", "state_management", "data_persistence", "realtime"]
    elif _contains_any(text, ["cms", "content management"]):
        domain = "content"
        app_type = "cms"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["pages", "posts", "editor", "admin"]
        required_capabilities = ["crud", "state_management", "data_persistence", "admin_panel"]
    elif _contains_any(text, ["dashboard"]) and _contains_any(text, ["backend", "database", "auth", "login"]):
        domain = "dashboard"
        app_type = "dashboard"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["dashboard", "charts", "auth", "database"]
        required_capabilities = ["state_management", "data_persistence", "backend_api", "reporting"]
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
    if _contains_any(text, ["crud", "create read update delete"]) and "crud" not in required_capabilities:
        required_capabilities.append("crud")
    if _contains_any(text, ["database", "db", "persist", "simpan data"]) and "data_persistence" not in required_capabilities:
        required_capabilities.append("data_persistence")

    return PlanSignature(
        domain=domain,
        intent=intent,
        app_type=app_type,
        complexity=complexity,
        feature_keywords=_unique(feature_keywords),
        required_capabilities=_unique(required_capabilities),
    )

