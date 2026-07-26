"""ATT&CK Enterprise technique mapping per incident category.

Every technique ID below was verified against the real Enterprise ATT&CK
STIX bundle, downloaded this session directly from MITRE's own official
GitHub CTI data repository — not recalled from training data:

    curl https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json

Dataset identity (checked, not assumed):
    Collection:        "Enterprise ATT&CK"
    Collection modified: 2026-05-12T14:00:00.188Z
    Total STIX objects: 25,843
    Active techniques:  697 (revoked and deprecated ones excluded)

Per-category source notes — the exact dataset entry each ID was checked
against (STIX object id + that object's own `modified` timestamp, both
read from the downloaded bundle, plus the canonical attack.mitre.org URL
for independent cross-check):

  BRUTE_FORCE
    T1110 "Brute Force"
      attack-pattern--a93494bb-4b80-4ea1-8695-3236a49916fd
      modified 2026-05-12T15:12:00.706Z
      https://attack.mitre.org/techniques/T1110

  PORT_SCAN
    T1595 "Active Scanning"
      attack-pattern--67073dde-d720-45ae-83da-b12d5e73ca3b
      modified 2025-10-24T17:48:53.018Z
      https://attack.mitre.org/techniques/T1595
    T1046 "Network Service Discovery"
      attack-pattern--e3a12395-188d-4051-9a16-ea8e14d07b88
      modified 2026-05-12T15:12:00.723Z
      https://attack.mitre.org/techniques/T1046

  MALWARE_EXECUTION
    T1204.002 "Malicious File" (sub-technique of T1204 User Execution —
    used instead of the parent because "malware signature match" is
    specifically about a malicious file, not user-execution in general)
      attack-pattern--232b7f21-adf9-4b42-b936-b9d6f7df856e
      modified 2026-05-12T15:12:00.623Z
      https://attack.mitre.org/techniques/T1204/002
    T1059 "Command and Scripting Interpreter"
      attack-pattern--7385dfaf-6886-4229-9ecd-6fd678040830
      modified 2026-05-12T15:12:00.641Z
      https://attack.mitre.org/techniques/T1059

  DENIAL_OF_SERVICE
    T1499 "Endpoint Denial of Service"
      attack-pattern--c675646d-e204-4aa8-978d-e3d6d65885c4
      modified 2025-10-24T17:49:22.088Z
      https://attack.mitre.org/techniques/T1499
    T1498.001 "Direct Network Flood" (sub-technique of T1498 Network
    Denial of Service — checked directly rather than recalled: this is
    NOT named "SYN Flood", which is what memory would have guessed)
      attack-pattern--0bda01d5-4c1d-4062-8ee2-6872334383c3
      modified 2025-10-24T17:48:22.567Z
      https://attack.mitre.org/techniques/T1498/001

  PRIVILEGE_ESCALATION
    T1548.003 "Sudo and Sudo Caching" (sub-technique of T1548 Abuse
    Elevation Control Mechanism — precise match for the "unauthorized
    sudo" keyword in core/detection/categories.py)
      attack-pattern--1365fe3b-0f50-455d-b4da-266ce31c23b0
      modified 2026-05-12T15:12:00.621Z
      https://attack.mitre.org/techniques/T1548/003
    T1068 "Exploitation for Privilege Escalation"
      attack-pattern--b21c3b2d-02e6-45b1-980b-e69051040839
      modified 2025-10-24T17:49:14.643Z
      https://attack.mitre.org/techniques/T1068

  DISCOVERY
    T1087 "Account Discovery"
      attack-pattern--72b74d71-8169-42aa-92e0-e7b04b9f5a08
      modified 2026-05-12T15:12:00.641Z
      https://attack.mitre.org/techniques/T1087
    T1083 "File and Directory Discovery"
      attack-pattern--7bc57495-ea59-4380-be31-a64af124ef18
      modified 2026-05-12T15:12:00.644Z
      https://attack.mitre.org/techniques/T1083

  UNCATEGORIZED
    No mapping — most syslog lines are ordinary system events, not
    attacks (see core/detection/categories.py). Forcing a technique onto
    an uncategorized incident would be a fabricated mapping, which is
    exactly what was to be avoided here.
"""

from dataclasses import dataclass

from data.models import IncidentCategory


@dataclass(frozen=True)
class MitreTechnique:
    technique_id: str
    name: str


CATEGORY_TECHNIQUES: dict[IncidentCategory, list[MitreTechnique]] = {
    IncidentCategory.BRUTE_FORCE: [
        MitreTechnique("T1110", "Brute Force"),
    ],
    IncidentCategory.PORT_SCAN: [
        MitreTechnique("T1595", "Active Scanning"),
        MitreTechnique("T1046", "Network Service Discovery"),
    ],
    IncidentCategory.MALWARE_EXECUTION: [
        MitreTechnique("T1204.002", "Malicious File"),
        MitreTechnique("T1059", "Command and Scripting Interpreter"),
    ],
    IncidentCategory.DENIAL_OF_SERVICE: [
        MitreTechnique("T1499", "Endpoint Denial of Service"),
        MitreTechnique("T1498.001", "Direct Network Flood"),
    ],
    IncidentCategory.PRIVILEGE_ESCALATION: [
        MitreTechnique("T1548.003", "Sudo and Sudo Caching"),
        MitreTechnique("T1068", "Exploitation for Privilege Escalation"),
    ],
    IncidentCategory.DISCOVERY: [
        MitreTechnique("T1087", "Account Discovery"),
        MitreTechnique("T1083", "File and Directory Discovery"),
    ],
    IncidentCategory.UNCATEGORIZED: [],
}


def techniques_for(category: IncidentCategory) -> list[MitreTechnique]:
    return CATEGORY_TECHNIQUES.get(category, [])
