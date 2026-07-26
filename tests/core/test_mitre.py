"""core/mitre.py — verifies every mapped technique ID against a real
extract of the ATT&CK dataset, not just ID-format shape.

tests/core/fixtures/mitre_technique_subset.json is a pruned subset of the
Enterprise ATT&CK STIX bundle, extracted programmatically (not hand-typed)
from the actual bundle downloaded this session directly from MITRE's
official GitHub CTI data repo — see core/mitre.py's module docstring for
full provenance (collection name/version, per-ID STIX object ids, and the
attack.mitre.org URL for independent cross-check). The full 53MB bundle
isn't committed; this fixture is the traceable, CI-safe stand-in for it —
regenerating it means re-running the extraction against a fresh download,
not editing this file by hand.
"""

import json
import re
from pathlib import Path

import pytest

from core.mitre import CATEGORY_TECHNIQUES, techniques_for
from data.models import IncidentCategory

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mitre_technique_subset.json"
_ATTACK_ID_RE = re.compile(r"^T\d{4}(\.\d{3})?$")


@pytest.fixture(scope="module")
def real_technique_data() -> dict:
    with open(FIXTURE_PATH) as f:
        return json.load(f)["techniques"]


def _all_mapped_techniques():
    for category, techniques in CATEGORY_TECHNIQUES.items():
        for technique in techniques:
            yield category, technique


@pytest.mark.parametrize(
    "category,technique",
    list(_all_mapped_techniques()),
    ids=lambda v: v.value if isinstance(v, IncidentCategory) else v.technique_id,
)
def test_technique_id_matches_attack_format(category, technique):
    assert _ATTACK_ID_RE.match(technique.technique_id), (
        f"{technique.technique_id} (category {category.value}) doesn't match ATT&CK ID format TNNNN or TNNNN.NNN"
    )


@pytest.mark.parametrize(
    "category,technique",
    list(_all_mapped_techniques()),
    ids=lambda v: v.value if isinstance(v, IncidentCategory) else v.technique_id,
)
def test_technique_exists_in_real_dataset_with_matching_name(category, technique, real_technique_data):
    real = real_technique_data.get(technique.technique_id)
    assert real is not None, (
        f"{technique.technique_id} (category {category.value}) was not found in the verified ATT&CK extract "
        f"— this would be exactly the fabricated-ID failure mode flagged as worse than no mapping at all"
    )
    assert real["name"] == technique.name, (
        f"{technique.technique_id}: core/mitre.py says {technique.name!r}, "
        f"but the verified dataset says {real['name']!r}"
    )


def test_every_category_has_an_entry_including_uncategorized():
    assert set(CATEGORY_TECHNIQUES.keys()) == set(IncidentCategory)


def test_uncategorized_has_no_mapping():
    # Not every incident is an attack — forcing a technique onto
    # UNCATEGORIZED would itself be a fabricated mapping.
    assert techniques_for(IncidentCategory.UNCATEGORIZED) == []


def test_every_attack_backed_category_has_at_least_one_technique():
    for category in IncidentCategory:
        if category is IncidentCategory.UNCATEGORIZED:
            continue
        assert len(techniques_for(category)) >= 1, category
