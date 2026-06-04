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
    "crud_app",
    "auth_app",
    "data_app",
    "saas",
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
    "item_schema": MissingDecision(
        key="item_schema",
        question="Field item/barang apa saja yang perlu dilacak?",
        default_recommendation="Start with name, SKU/category, quantity, and status for inventory MVP.",
        risk=RiskLevel.MEDIUM,
    ),
    "stock_movement_rules": MissingDecision(
        key="stock_movement_rules",
        question="Bagaimana aturan stok bertambah/berkurang dan kapan stok dianggap rendah?",
        default_recommendation="Use manual stock adjustment and a simple low-stock threshold for MVP.",
        risk=RiskLevel.MEDIUM,
    ),
    "product_schema": MissingDecision(
        key="product_schema",
        question="Field produk apa saja yang wajib ada untuk marketplace MVP?",
        default_recommendation="Start with name, price, image placeholder, stock, and description.",
        risk=RiskLevel.MEDIUM,
    ),
    "cart_checkout_scope": MissingDecision(
        key="cart_checkout_scope",
        question="Checkout cukup simulasi atau perlu alur order/pembayaran nyata?",
        default_recommendation="Use simulated checkout for MVP.",
        risk=RiskLevel.HIGH,
    ),
    "auth_type": MissingDecision(
        key="auth_type",
        question="Jenis login apa yang dibutuhkan: mock login, email/password lokal, atau backend auth?",
        default_recommendation="Use mock/local login for MVP unless backend auth is explicitly required.",
        risk=RiskLevel.HIGH,
    ),
    "session_persistence": MissingDecision(
        key="session_persistence",
        question="Session login perlu disimpan di mana dan berapa lama?",
        default_recommendation="Use local session state for MVP.",
        risk=RiskLevel.MEDIUM,
    ),
    "roles": MissingDecision(
        key="roles",
        question="Role pengguna apa saja yang dibutuhkan?",
        default_recommendation="Start with a single admin/user distinction for MVP if roles are needed.",
        risk=RiskLevel.MEDIUM,
    ),
    "crud_scope": MissingDecision(
        key="crud_scope",
        question="CRUD ini untuk entitas apa, misalnya produk, user, todo, atau transaksi?",
        default_recommendation="Limit CRUD to the primary MVP entity first.",
        risk=RiskLevel.MEDIUM,
    ),
    "entity": MissingDecision(
        key="entity",
        question="Entitas utama apa yang harus dikelola oleh CRUD ini?",
        default_recommendation="Pick one primary entity for the first MVP screen.",
        risk=RiskLevel.MEDIUM,
    ),
    "schema_fields": MissingDecision(
        key="schema_fields",
        question="Field apa saja yang harus dimiliki entitas tersebut?",
        default_recommendation="Start with 3-5 essential fields for the primary entity.",
        risk=RiskLevel.MEDIUM,
    ),
    "storage_type": MissingDecision(
        key="storage_type",
        question="Data disimpan di mana: local state, localStorage, JSON, SQL, database, atau backend API?",
        default_recommendation="Use browser/local persistence for MVP unless backend persistence is required.",
        risk=RiskLevel.MEDIUM,
    ),
    "persistence": MissingDecision(
        key="persistence",
        question="Apakah CRUD ini hanya simulasi frontend atau harus persistent?",
        default_recommendation="Use localStorage persistence for a safe MVP unless real backend persistence is explicitly required.",
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
    "marketplace": ["roles", "product_schema", "cart_checkout_scope", "payment", "database", "admin_panel", "crud_scope"],
    "inventory": ["item_schema", "stock_movement_rules", "storage_type", "database", "roles", "reporting_analytics"],
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
    "crud_app": ["crud_scope", "entity", "schema_fields", "storage_type", "persistence", "backend_api"],
    "auth_app": ["auth_type", "roles", "session_persistence", "backend_api", "database"],
    "data_app": ["database", "storage_type", "schema_fields", "backend_api", "persistence"],
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
        "item_schema": ["item", "barang", "sku", "quantity", "jumlah", "stok", "stock", "category", "kategori"],
        "stock_movement_rules": ["masuk", "keluar", "adjustment", "threshold", "low stock", "stok rendah", "restock"],
        "product_schema": ["produk", "product", "price", "harga", "stock", "stok", "description", "deskripsi"],
        "cart_checkout_scope": ["cart", "keranjang", "checkout", "order", "pesanan", "payment", "pembayaran", "simulasi"],
        "auth_type": ["mock login", "email", "password", "oauth", "backend auth", "firebase", "supabase"],
        "session_persistence": ["session", "token", "remember", "local storage", "localstorage", "cookie"],
        "crud_scope": ["todo", "task", "produk", "product", "barang", "item", "user", "customer", "employee", "student", "book", "order", "transaction", "transaksi"],
        "entity": ["todo", "task", "produk", "product", "barang", "item", "user", "customer", "employee", "student", "book", "order", "transaction", "transaksi"],
        "schema_fields": ["field", "fields", "kolom", "atribut", "name", "nama", "title", "judul", "description", "deskripsi", "status", "price", "harga", "email"],
        "storage_type": ["local storage", "localstorage", "local state", "state lokal", "json", "database", "db", "sql", "mysql", "postgres", "sqlite", "backend", "api"],
        "persistence": ["local storage", "localstorage", "persist", "persistent", "persistence", "simpan", "database", "db", "sql", "json"],
    }
    return any(term in text for term in hints.get(key, [key]))


def analyze_scope(prompt: str, signature: PlanSignature) -> ScopeAnalysis:
    is_broad = signature.app_type in BROAD_APP_TYPES or signature.complexity == ComplexityLevel.HIGH
    missing_decisions: list[MissingDecision] = []

    if is_broad:
        from backend.brain.dss_engine import DSS_OPTIONS
        from backend.brain.schemas import DecisionOption
        
        keys = APP_DECISION_KEYS.get(signature.app_type, ["authentication", "database", "roles", "crud_scope"])
        for key in keys:
            if key in DECISION_LIBRARY and not _prompt_mentions_decision(prompt, key):
                dec = DECISION_LIBRARY[key]
                options_list = []
                raw_options = DSS_OPTIONS.get(key, ["Yes, implement this", "No, skip this", "Simulate/Mock this"])
                for opt in raw_options:
                    is_rec = "Recommended" in opt or "localStorage" in opt or "Mock" in opt or "Placeholder" in opt
                    options_list.append(DecisionOption(
                        text=opt,
                        score=9.0 if is_rec else 5.0,
                        is_recommended=is_rec
                    ))
                missing_decisions.append(MissingDecision(
                    key=dec.key,
                    question=dec.question,
                    default_recommendation=dec.default_recommendation,
                    risk=dec.risk,
                    options=options_list
                ))

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
