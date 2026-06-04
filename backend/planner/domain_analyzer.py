import logging
import json
from typing import List, Dict
from pydantic import BaseModel
from backend.services.ai_service import complete

logger = logging.getLogger(__name__)

class EntityField(BaseModel):
    name: str
    type: str

class DomainEntity(BaseModel):
    name: str
    fields: List[EntityField]

class Subdomain(BaseModel):
    name: str
    description: str
    entities: List[DomainEntity]

def analyze_domain(prompt: str) -> List[Subdomain]:
    """
    Decomposes the user prompt into bounded contexts/subdomains and core entities (DDD Thinking).
    """
    sys_prompt = "You are a Domain-Driven Design (DDD) architect. Identify bounded subdomains and core entities."
    user_prompt = (
        f"Based on this user prompt: '{prompt}', please decompose the system into 2-3 bounded contexts/subdomains.\n"
        f"For each subdomain, provide:\n"
        f"1. Subdomain Name (e.g., 'Catalog Management')\n"
        f"2. Brief description (e.g., 'Handles product inventory and price updates')\n"
        f"3. Core entity name (e.g., 'Product')\n"
        f"4. Core fields (name and type, e.g., 'id: string, name: string, price: number')\n\n"
        f"Format response EXACTLY as a valid JSON list like:\n"
        f"[\n"
        f"  {{\n"
        f"    \"name\": \"Catalog Management\",\n"
        f"    \"description\": \"Handles products catalog\",\n"
        f"    \"entities\": [\n"
        f"      {{\n"
        f"        \"name\": \"Product\",\n"
        f"        \"fields\": [\n"
        f"          {{\"name\": \"id\", \"type\": \"string\"}},\n"
        f"          {{\"name\": \"name\", \"type\": \"string\"}}\n"
        f"        ]\n"
        f"      }}\n"
        f"    ]\n"
        f"  }}\n"
        f"]"
    )
    
    try:
        raw_json = complete(sys_prompt, user_prompt, max_tokens=1000, temperature=0.2)
        # Parse JSON block
        start_idx = raw_json.find("[")
        end_idx = raw_json.rfind("]") + 1
        if start_idx != -1 and end_idx != 0:
            json_str = raw_json[start_idx:end_idx]
            data = json.loads(json_str)
            subdomains = []
            for item in data:
                entities = []
                for ent in item.get("entities", []):
                    fields = [EntityField(name=f.get("name"), type=f.get("type")) for f in ent.get("fields", [])]
                    entities.append(DomainEntity(name=ent.get("name"), fields=fields))
                subdomains.append(Subdomain(
                    name=item.get("name"),
                    description=item.get("description"),
                    entities=entities
                ))
            return subdomains
    except Exception as e:
        logger.exception("Failed to analyze domain using LLM, using fallback template: %s", e)
        
    # Fallback template
    return [
        Subdomain(
            name="State Domain",
            description="Core client-side state and browser persistence logic",
            entities=[
                DomainEntity(
                    name="ApplicationState",
                    fields=[
                        EntityField(name="items", type="array"),
                        EntityField(name="isLoading", type="boolean")
                    ]
                )
            ]
        ),
        Subdomain(
            name="Primary Domain",
            description="Main entity CRUD management boundary",
            entities=[
                DomainEntity(
                    name="Item",
                    fields=[
                        EntityField(name="id", type="string"),
                        EntityField(name="name", type="string"),
                        EntityField(name="timestamp", type="number")
                    ]
                )
            ]
        )
    ]
