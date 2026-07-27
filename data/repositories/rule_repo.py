"""Alert rule persistence: rule definitions and the match-history that
makes re-evaluation idempotent. Zero Qt imports — see CLAUDE.md, Layering.
"""

import json
import sqlite3
from dataclasses import replace
from datetime import datetime

from data.models import AlertRule, Condition, ConditionField, ConditionOperator


class RuleRepository:
    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection

    # -- rule CRUD ------------------------------------------------------------

    def insert_rule(self, rule: AlertRule) -> AlertRule:
        cur = self._conn.execute(
            "INSERT INTO alert_rules (name, enabled, conditions) VALUES (?, ?, ?)",
            (rule.name, int(rule.enabled), self._encode_conditions(rule.conditions)),
        )
        self._conn.commit()
        return replace(rule, id=cur.lastrowid)

    def update_rule(self, rule: AlertRule) -> AlertRule:
        self._conn.execute(
            "UPDATE alert_rules SET name = ?, enabled = ?, conditions = ? WHERE id = ?",
            (rule.name, int(rule.enabled), self._encode_conditions(rule.conditions), rule.id),
        )
        self._conn.commit()
        return rule

    def set_enabled(self, rule_id: int, enabled: bool) -> None:
        self._conn.execute("UPDATE alert_rules SET enabled = ? WHERE id = ?", (int(enabled), rule_id))
        self._conn.commit()

    def delete_rule(self, rule_id: int) -> None:
        self._conn.execute("DELETE FROM alert_matches WHERE rule_id = ?", (rule_id,))
        self._conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
        self._conn.commit()

    def get_rule(self, rule_id: int) -> AlertRule | None:
        row = self._conn.execute("SELECT * FROM alert_rules WHERE id = ?", (rule_id,)).fetchone()
        return self._row_to_rule(row) if row else None

    def list_rules(self) -> list[AlertRule]:
        rows = self._conn.execute("SELECT * FROM alert_rules ORDER BY id").fetchall()
        return [self._row_to_rule(row) for row in rows]

    def list_enabled_rules(self) -> list[AlertRule]:
        rows = self._conn.execute("SELECT * FROM alert_rules WHERE enabled = 1 ORDER BY id").fetchall()
        return [self._row_to_rule(row) for row in rows]

    # -- match history (append-only, deduplicated) -----------------------------

    def record_match(self, rule_id: int, incident_id: int) -> bool:
        """Records a rule match. Returns True if this was a new match,
        False if this exact (rule, incident) pair was already recorded —
        the UNIQUE constraint on alert_matches (see data/db.py) is what
        makes re-evaluation idempotent instead of writing a duplicate row."""
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO alert_matches (rule_id, incident_id, matched_at) VALUES (?, ?, ?)",
            (rule_id, incident_id, datetime.now().isoformat()),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def match_count(self, rule_id: int | None = None) -> int:
        if rule_id is None:
            return self._conn.execute("SELECT COUNT(*) FROM alert_matches").fetchone()[0]
        return self._conn.execute(
            "SELECT COUNT(*) FROM alert_matches WHERE rule_id = ?", (rule_id,)
        ).fetchone()[0]

    def has_matched(self, rule_id: int, incident_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM alert_matches WHERE rule_id = ? AND incident_id = ?",
            (rule_id, incident_id),
        ).fetchone()
        return row is not None

    # -- encoding ---------------------------------------------------------------

    @staticmethod
    def _encode_conditions(conditions: list[Condition]) -> str:
        return json.dumps(
            [{"field": c.field.value, "operator": c.operator.value, "value": c.value} for c in conditions]
        )

    @staticmethod
    def _decode_conditions(raw: str) -> list[Condition]:
        return [
            Condition(field=ConditionField(d["field"]), operator=ConditionOperator(d["operator"]), value=d["value"])
            for d in json.loads(raw)
        ]

    def _row_to_rule(self, row: sqlite3.Row) -> AlertRule:
        return AlertRule(
            id=row["id"],
            name=row["name"],
            enabled=bool(row["enabled"]),
            conditions=self._decode_conditions(row["conditions"]),
        )
