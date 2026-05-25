from backend.brain.schemas import ComplexityLevel, MissingDecision, PlanSignature, RiskLevel, ScopeAnalysis


BROAD_APP_TYPES = {
    "marketplace",
    "inventory",
    "lms",
    "cms",
    "recruitment",
    "finance",
    "accounting",
    "social media",
    "booking",
    "pos",
    "erp",
    "crm",
    "e-commerce",
    "dashboard",
}


DECISION_LIBRARY = {
    "authentication": MissingDecision(
        key="authentication",
        question="Apakah aplikasi membutuhkan login/authentication?",
        default_recommendation="Use simple local/mock auth for MVP unless real backend auth is explicitly required.",
        risk=RiskLevel.HIGH,
    ),
    "database": MissingDecision(
        key="database",
        question="Data apa yang perlu disimpan dan apakah perlu database nyata?",
        default_recommendation="Use local persistence or seeded mock data for MVP unless durable backend storage is explicitly required.",
        risk=RiskLevel.HIGH,
    ),
    "roles": MissingDecision(
        key="roles",
        question="Role pengguna apa saja yang dibutuhkan?",
        default_recommendation="Start with a single admin/user distinction for MVP if roles are needed.",
        risk=RiskLevel.MEDIUM,
    ),
    "crud_scope": MissingDecision(
        key="crud_scope",
        question="Entity mana saja yang harus bisa dibuat, diedit, dan dihapus?",
        default_recommendation="Limit CRUD to the primary MVP entity first.",
        risk=RiskLevel.MEDIUM,
    ),
    "storage_type": MissingDecision(
        key="storage_type",
        question="Apakah penyimpanan cukup lokal/mock atau harus tersambung backend?",
        default_recommendation="Use browser/local persistence for MVP unless backend persistence is required.",
        risk=RiskLevel.MEDIUM,
    ),
    "backend_api": MissingDecision(
        key="backend_api",
        question="Apakah aplikasi membutuhkan API backend sungguhan?",
        default_recommendation="Keep API calls mocked locally for MVP unless integration is explicitly required.",
        risk=RiskLevel.HIGH,
    ),
    "payment": MissingDecision(
        key="payment",
        question="Apakah checkout membutuhkan pembayaran nyata atau simulasi?",
        default_recommendation="Use simulated checkout for MVP and avoid real payment integration.",
        risk=RiskLevel.HIGH,
    ),
    "admin_panel": MissingDecision(
        key="admin_panel",
        question="Fitur admin apa yang wajib ada untuk MVP?",
        default_recommendation="Use a simple admin CRUD screen for the main entity.",
        risk=RiskLevel.MEDIUM,
    ),
    "reporting_analytics": MissingDecision(
        key="reporting_analytics",
        question="Laporan atau analytics apa yang paling penting untuk MVP?",
        default_recommendation="Start with one simple summary metric or table.",
        risk=RiskLevel.MEDIUM,
    ),
    "file_upload": MissingDecision(
        key="file_upload",
        question="Apakah aplikasi membutuhkan upload file atau gambar?",
        default_recommendation="Use placeholder assets for MVP unless uploads are core to the product.",
        risk=RiskLevel.MEDIUM,
    ),
    "realtime": MissingDecision(
        key="realtime",
        question="Apakah data perlu realtime atau cukup refresh manual?",
        default_recommendation="Use static/local state for MVP unless realtime is explicitly required.",
        risk=RiskLevel.MEDIUM,
    ),
    "deployment_target": MissingDecision(
        key="deployment_target",
        question="Target deployment apa yang diinginkan?",
        default_recommendation="Defer deployment-specific choices until after MVP behavior is confirmed.",
        risk=RiskLevel.LOW,
    ),
    "external_dependencies": MissingDecision(
        key="external_dependencies",
        question="Integrasi eksternal apa yang wajib tersedia?",
        default_recommendation="Avoid external dependencies in MVP unless they are essential.",
        risk=RiskLevel.MEDIUM,
    ),
}


APP_DECISION_KEYS = {
    "marketplace": ["authentication", "database", "roles", "payment", "admin_panel", "crud_scope"],
    "inventory": ["authentication", "database", "roles", "crud_scope", "storage_type", "reporting_analytics"],
    "lms": ["authentication", "database", "roles", "crud_scope", "file_upload", "reporting_analytics"],
    "cms": ["authentication", "database", "roles", "admin_panel", "file_upload", "deployment_target"],
    "recruitment": ["authentication", "database", "roles", "crud_scope", "file_upload", "reporting_analytics"],
    "finance": ["authentication", "database", "roles", "reporting_analytics", "external_dependencies"],
    "crm": ["authentication", "database", "roles", "crud_scope", "reporting_analytics"],
    "erp": ["authentication", "database", "roles", "crud_scope", "reporting_analytics", "external_dependencies"],
    "pos": ["authentication", "database", "roles", "payment", "reporting_analytics"],
    "booking": ["authentication", "database", "roles", "realtime", "external_dependencies"],
    "social media": ["authentication", "database", "roles", "file_upload", "realtime"],
    "dashboard": ["authentication", "database", "backend_api", "roles", "reporting_analytics"],
}


def _prompt_mentions_decision(prompt: str, key: str) -> bool:
    text = prompt.lower()
    hints = {
        "authentication": ["login", "auth", "authentication", "register", "user"],
        "database": ["database", "db", "postgres", "mysql", "sqlite", "supabase", "firebase"],
        "roles": ["role", "admin", "user", "permission"],
        "payment": ["payment", "pembayaran", "stripe", "midtrans", "checkout"],
        "file_upload": ["upload", "file", "gambar", "image"],
        "realtime": ["realtime", "real-time", "socket", "live"],
        "deployment_target": ["deploy", "deployment", "hosting", "vercel"],
        "external_dependencies": ["integrasi", "api eksternal", "third party"],
        "backend_api": ["backend", "api"],
    }
    return any(term in text for term in hints.get(key, [key]))


def analyze_scope(prompt: str, signature: PlanSignature) -> ScopeAnalysis:
    is_broad = signature.app_type in BROAD_APP_TYPES or signature.complexity == ComplexityLevel.HIGH
    missing_decisions: list[MissingDecision] = []

    if is_broad:
        keys = APP_DECISION_KEYS.get(signature.app_type, ["authentication", "database", "roles", "crud_scope"])
        for key in keys:
            if key in DECISION_LIBRARY and not _prompt_mentions_decision(prompt, key):
                missing_decisions.append(DECISION_LIBRARY[key])

    if not is_broad:
        risk_level = RiskLevel.LOW
    elif any(decision.risk == RiskLevel.HIGH for decision in missing_decisions):
        risk_level = RiskLevel.HIGH
    else:
        risk_level = RiskLevel.MEDIUM

    return ScopeAnalysis(
        is_broad=is_broad,
        risk_level=risk_level,
        missing_decisions=missing_decisions,
    )

