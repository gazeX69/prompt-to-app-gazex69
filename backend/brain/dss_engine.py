from typing import Any, Dict, List
from backend.brain.schemas import MissingDecision, RiskLevel

DSS_OPTIONS = {
    "authentication": [
        "Mock/Local Login (Recommended for MVP)",
        "Durable Database Login",
        "No authentication required"
    ],
    "database": [
        "Browser LocalStorage (Recommended for MVP)",
        "In-Memory State (Reset on reload)",
        "Persistent Backend Database"
    ],
    "payment": [
        "Simulated Checkout (Recommended for MVP)",
        "Stripe Sandbox Integration",
        "Cash on Delivery / Manual Payment"
    ],
    "cart_checkout_scope": [
        "Simulated local checkout (Recommended for MVP)",
        "Real checkout with order persistence"
    ],
    "roles": [
        "Single Admin Role (Recommended for MVP)",
        "Multi-role (Admin, Manager, User)",
        "No user roles required"
    ],
    "storage_type": [
        "LocalStorage (Recommended)",
        "JSON file persistence",
        "Relational SQL database"
    ],
    "persistence": [
        "localStorage persistent (Recommended)",
        "Mock only (No persistence)",
        "Backend API persistent"
    ],
    "backend_api": [
        "Mock API local client (Recommended for MVP)",
        "Full FastAPI backend integration"
    ],
    "admin_panel": [
        "Simple Admin Screen (Recommended)",
        "Advanced Analytics & Management",
        "No Admin Panel required"
    ],
    "reporting_analytics": [
        "Simple summary metrics cards (Recommended)",
        "Interactive Charts/Graph view",
        "No reporting required"
    ],
    "file_upload": [
        "Placeholder image URLs (Recommended for MVP)",
        "Local filesystem upload (base64)",
        "Cloud Storage (AWS S3, etc.)"
    ],
    "realtime": [
        "Manual poll/refresh (Recommended for MVP)",
        "WebSocket connection",
        "No real-time features"
    ],
}

def _option_score(option_text: str, decision: MissingDecision) -> dict:
    text = option_text.lower()
    is_safe_mvp = any(
        marker in text
        for marker in [
            "recommended",
            "localstorage",
            "mock",
            "placeholder",
            "simulated",
            "summary metrics",
            "manual",
        ]
    )
    is_external_or_durable = any(
        marker in text
        for marker in [
            "stripe",
            "cloud",
            "backend",
            "database",
            "websocket",
            "sql",
            "advanced",
            "real checkout",
        ]
    )

    data_score = 0.86 if is_safe_mvp else 0.58
    knowledge_score = 0.84 if is_safe_mvp else 0.64
    rules_score = 0.9 if is_safe_mvp else 0.55

    if decision.risk == RiskLevel.HIGH and is_external_or_durable and not is_safe_mvp:
        rules_score -= 0.18
        knowledge_score -= 0.08

    final_score = (0.4 * data_score) + (0.3 * knowledge_score) + (0.3 * rules_score)
    return {
        "score": round(max(0.0, min(1.0, final_score)), 2),
        "is_recommended": final_score >= 0.75,
        "criteria": {
            "data": round(data_score, 2),
            "knowledge": round(knowledge_score, 2),
            "rules": round(rules_score, 2),
        },
    }


def get_dss_recommendations(missing_decisions: List[MissingDecision]) -> List[Dict[str, Any]]:
    """
    Enriches missing decisions with predefined options and recommendation scores.
    DecisionScore = 0.4(Data) + 0.3(Knowledge) + 0.3(Rules)
    """
    recommendations = []
    
    for decision in missing_decisions:
        key = decision.key
        options = DSS_OPTIONS.get(key, ["Yes, implement this", "No, skip this", "Simulate/Mock this"])
        
        option_details = []
        for opt in options:
            scoring = _option_score(opt, decision)
            option_details.append({
                "text": opt,
                "score": scoring["score"],
                "is_recommended": scoring["is_recommended"],
                "criteria": scoring["criteria"],
            })
            
        recommendations.append({
            "key": key,
            "question": decision.question,
            "default_recommendation": decision.default_recommendation,
            "risk": decision.risk,
            "options": option_details,
            "method": "Weighted DSS/SPK: 0.4 data fit + 0.3 case knowledge + 0.3 safety rules",
        })
        
    return recommendations
