"""Auto-summarize key facts at session end and persist to PersonalMemory.

Triggered in Store.save() when running transitions from True → False (turn complete).
Extracts at most 3–5 facts: parameters used, decisions made, results obtained.
Uses keyword extraction only (no LLM call) to keep it fast and offline-safe.
"""
import re
from .storage import now


# Patterns that indicate a fact worth remembering.
_FACT_PATTERNS = [
    # Engineering parameters
    (re.compile(
        r'(?:γ|gamma|dung trọng|unit weight)[^=\n]*[=:]\s*(\d[\d.,]*)(?:\s*kN/m[²³³]?)?',
        re.I,
    ), 'thông số {match}'),
    (re.compile(
        r'(?:φ|phi|góc ma sát|friction angle)[^=\n]*[=:]\s*(\d[\d.,]*)(?:°|deg)?',
        re.I,
    ), 'thông số {match}'),
    (re.compile(
        r'(?:c\b|cohesion|lực dính)[^=\n]*[=:]\s*(\d[\d.,]*)(?:\s*kPa|kN)?',
        re.I,
    ), 'thông số {match}'),
    # Results
    (re.compile(
        r'(?:FS|factor.of.safety|hệ số ổn định)\s*[=:≈~]\s*(\d[\d.,]*)',
        re.I,
    ), 'kết quả FS={match}'),
    (re.compile(
        r'(?:lún|settlement|độ lún)\s*[=:≈~]\s*(\d[\d.,]*)(?:\s*mm|cm|m)?',
        re.I,
    ), 'kết quả lún={match}'),
    (re.compile(
        r'(?:chuyển vị|displacement)\s*[=:≈~]\s*(\d[\d.,]*)(?:\s*mm|cm|m)?',
        re.I,
    ), 'kết quả displacement={match}'),
    # Software mentions
    (re.compile(r'\bPLAXIS\s+([23]D)\b', re.I), 'phần mềm PLAXIS {match}'),
    (re.compile(r'\bGeoSlope\b', re.I), 'phần mềm GeoSlope'),
]

_MIN_MESSAGES = 4  # Don't summarize trivially short conversations.
_MAX_FACTS = 5


def _extract_facts(messages):
    """Pull key facts from conversation text without an LLM call."""
    text = '\n'.join(
        m.get('content', '') for m in messages
        if m.get('role') in ('user', 'assistant') and isinstance(m.get('content'), str)
    )
    if not text.strip():
        return []
    facts = []
    seen = set()
    for pattern, template in _FACT_PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groups()
            value = groups[0] if groups else match.group(0)[:60]
            label = template.format(match=value)
            key = label.casefold()
            if key not in seen:
                facts.append(label)
                seen.add(key)
            if len(facts) >= _MAX_FACTS:
                return facts
    return facts


def _build_summary(state):
    """Return a one-line summary suitable for PersonalMemory, or None."""
    messages = state.get('messages', [])
    if len(messages) < _MIN_MESSAGES:
        return None
    # First user message as the topic.
    topic = next(
        (m.get('content', '')[:120] for m in messages if m.get('role') == 'user'),
        '',
    ).strip()
    if not topic:
        return None
    facts = _extract_facts(messages)
    if not facts:
        return None
    return 'Phiên làm việc: ' + topic + '. ' + '; '.join(facts)


def auto_save_session(store, state):
    """Called by Store.save() when a turn completes. Persists a brief session summary."""
    owner = state.get('account_username')
    if not owner:
        return
    # Only summarize when AI finishes a turn (running just became False) and
    # there are enough messages to be meaningful.
    if state.get('running'):
        return
    messages = state.get('messages', [])
    if len(messages) < _MIN_MESSAGES:
        return
    # Avoid duplicating the same session summary.
    last_user = next(
        (m.get('content', '') for m in reversed(messages) if m.get('role') == 'user'),
        '',
    )
    if not last_user.strip():
        return
    summary = _build_summary(state)
    if not summary:
        return
    # Use PersonalMemory; identifier derived from summary text for deduplication.
    try:
        from .memory import PersonalMemory
        mem = PersonalMemory(store, None, owner)
        mem.put(summary, title='Tóm tắt phiên làm việc')
    except Exception:
        pass
