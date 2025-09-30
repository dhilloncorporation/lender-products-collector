"""Financial product schemas - Reference only."""

import json
from pathlib import Path
from typing import Dict, Any

def load_reference_schema() -> Dict[str, Any]:
    """Load the BIAN financial product reference schema."""
    schema_path = Path(__file__).parent / "bian_financial_product_schema.json"
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)

__all__ = [
    "load_reference_schema"
]
