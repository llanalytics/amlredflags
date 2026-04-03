from __future__ import annotations


KEYWORD_RULES = [
    {
        "category": "Sanctions",
        "severity": "high",
        "keywords": ["sanction", "ofac", "blocked person", "embargo"],
        "text": "Potential sanctions-related indicator detected.",
        "confidence_score": 90,
    },
    {
        "category": "Structuring",
        "severity": "high",
        "keywords": ["structuring", "smurfing", "threshold", "cash deposit"],
        "text": "Potential structuring behavior indicator detected.",
        "confidence_score": 85,
    },
    {
        "category": "Fraud",
        "severity": "medium",
        "keywords": ["fraud", "suspicious", "deceptive", "misrepresent"],
        "text": "Potential fraud-related indicator detected.",
        "confidence_score": 75,
    },
    {
        "category": "Enforcement Action",
        "severity": "medium",
        "keywords": ["enforcement action", "civil money penalty", "consent order"],
        "text": "Potential compliance enforcement indicator detected.",
        "confidence_score": 70,
    },
]


def extract_red_flags(text: str) -> list[dict]:
    lowered = text.lower()
    results: list[dict] = []

    for rule in KEYWORD_RULES:
        if any(keyword in lowered for keyword in rule["keywords"]):
            results.append(
                {
                    "category": rule["category"],
                    "severity": rule["severity"],
                    "text": rule["text"],
                    "confidence_score": rule["confidence_score"],
                }
            )

    return results
