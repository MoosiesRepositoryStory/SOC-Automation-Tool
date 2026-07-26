"""Category inference for the parsers — the logic half of the shared
taxonomy. The enum type itself lives in data/models.py (see IncidentCategory
there for why); this module holds keyword-inference for free-text sources
(syslog) and a strict mapping helper for structured sources (JSON/CSV) that
already name a category, so both land on the exact same vocabulary instead
of drifting apart.
"""

from data.models import IncidentCategory

# keyword -> category, checked as substrings against lowercased text.
# Categories are checked in _CATEGORY_ORDER below (first match wins), so
# more specific/higher-signal categories are listed earlier where keyword
# sets could overlap on the same message.
_KEYWORDS: dict[IncidentCategory, tuple[str, ...]] = {
    IncidentCategory.MALWARE_EXECUTION: (
        "malware",
        "ransomware",
        "trojan",
        "virus signature",
        "signature match",
        "malicious file",
    ),
    IncidentCategory.BRUTE_FORCE: (
        "failed password",
        "authentication failure",
        "invalid password",
        "failed login",
        "login failed",
    ),
    IncidentCategory.PORT_SCAN: (
        "port scan",
        "nmap",
        "scan detected",
        "scanning ports",
    ),
    IncidentCategory.DISCOVERY: (
        "enumeration",
        "reconnaissance",
        "network discovery",
        "host discovery",
        "directory listing",
    ),
    IncidentCategory.PRIVILEGE_ESCALATION: (
        "privilege escalation",
        "escalated privileges",
        "gained root",
        "unauthorized sudo",
        "setuid exploit",
    ),
    IncidentCategory.DENIAL_OF_SERVICE: (
        "denial of service",
        "dos attack",
        "syn flood",
        "resource exhaustion",
        "traffic flood",
    ),
}

_CATEGORY_ORDER = (
    IncidentCategory.MALWARE_EXECUTION,
    IncidentCategory.BRUTE_FORCE,
    IncidentCategory.PORT_SCAN,
    IncidentCategory.DISCOVERY,
    IncidentCategory.PRIVILEGE_ESCALATION,
    IncidentCategory.DENIAL_OF_SERVICE,
)


def infer_category_from_text(message: str) -> IncidentCategory:
    """For free-text log messages (syslog) with no dedicated category
    field. Same pattern as infer_severity_from_text in
    core/detection/parsers/common.py: substring keyword search, first
    category (in priority order) with a match wins. Most syslog lines are
    ordinary system events, not attacks — UNCATEGORIZED is the expected,
    correct outcome for those, not a failure to classify."""
    lowered = message.lower()
    for category in _CATEGORY_ORDER:
        if any(kw in lowered for kw in _KEYWORDS[category]):
            return category
    return IncidentCategory.UNCATEGORIZED


def parse_category(value: str | None) -> IncidentCategory:
    """For structured input (JSON/CSV) that already names a category.
    Deliberately NOT keyword-inference — only maps a value the source
    actually provided onto the shared enum. Accepts the enum's value
    string case/separator-insensitively; anything unrecognized becomes
    UNCATEGORIZED rather than silently inventing a new bucket."""
    if not value:
        return IncidentCategory.UNCATEGORIZED
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    try:
        return IncidentCategory(normalized)
    except ValueError:
        return IncidentCategory.UNCATEGORIZED
