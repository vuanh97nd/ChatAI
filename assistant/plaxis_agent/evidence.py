"""Deterministic acceptance checks: prose is never calculation evidence."""
import math
from typing import Any


def review(events: list[dict[str, Any]], criteria: list[Any]) -> dict[str, Any]:
    checks = []
    for criterion in criteria:
        observation = next((e['result'] for e in reversed(events)
                            if e.get('result', {}).get('ok') and
                            criterion.metric in e['result'].get('metrics', {})), {})
        metric = observation.get('metrics', {}).get(criterion.metric, {})
        value = metric.get('value')
        valid = (type(value) in (int, float) and math.isfinite(value) and
                 metric.get('unit') == criterion.unit and
                 not observation.get('preliminary_only', False))
        passed = valid and (value <= criterion.target if criterion.operator == 'le'
                            else value >= criterion.target)
        checks.append({'metric': criterion.metric, 'value': value,
                       'unit': criterion.unit, 'target': criterion.target,
                       'passed': bool(passed), 'evidence_valid': bool(valid)})
    return {'passed': bool(checks) and all(c['passed'] for c in checks),
            'checks': checks, 'scope': 'Numeric criteria only; not whole-model verification.'}
