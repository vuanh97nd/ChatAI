"""Unit tests for plaxis_agent optimisations."""
import json
import pytest
from assistant.plaxis_agent.model_config import select_tier, flash_config, reasoning_config
from assistant.plaxis_agent.evidence import review
from assistant.plaxis_agent.tools import _truncate_result, DESCRIPTIONS
from assistant.plaxis_agent.project_memory import _compact_event, _MAX_EVENTS
from assistant.plaxis_agent.agent import SYSTEM, _build_human_message
from assistant.plaxis_agent.schemas import Criterion


# ---------------------------------------------------------------------------
# model_config
# ---------------------------------------------------------------------------

def test_select_tier_defaults_to_flash():
    assert select_tier('inspect dự án', max_steps=4) == 'flash'


def test_select_tier_explicit_flash():
    assert select_tier('inspect', max_steps=12, model_tier='flash') == 'flash'


def test_select_tier_explicit_reasoning():
    assert select_tier('inspect', max_steps=4, model_tier='reasoning') == 'reasoning'


def test_select_tier_high_steps_forces_reasoning():
    assert select_tier('inspect', max_steps=8) == 'reasoning'


def test_select_tier_keyword_hố_đào():
    assert select_tier('Thiết kế hố đào 3 tầng', max_steps=4) == 'reasoning'


def test_select_tier_keyword_móng_cọc():
    assert select_tier('Tính móng cọc nhồi đường kính 600mm', max_steps=5) == 'reasoning'


def test_flash_config_max_tokens():
    assert flash_config().max_tokens == 512


def test_reasoning_config_max_tokens():
    assert reasoning_config().max_tokens == 1024


# ---------------------------------------------------------------------------
# evidence.review  (origin/main structure: 'checks' not 'items')
# ---------------------------------------------------------------------------

def _c(metric, op, target, unit='m'):
    return Criterion(metric=metric, operator=op, target=target, unit=unit)


def test_review_no_criteria():
    result = review([], [])
    # origin/main: bool([]) = False — no checks run is not "passed"
    assert result['passed'] is False
    assert result['checks'] == []


def test_review_metric_missing():
    result = review([], [_c('S_mm', 'le', 50, 'mm')])
    assert result['passed'] is False
    assert result['checks'][0]['passed'] is False
    assert result['checks'][0]['evidence_valid'] is False


def test_review_passes():
    events = [{'result': {'ok': True, 'metrics': {'S_mm': {'value': 30, 'unit': 'mm'}}}}]
    result = review(events, [_c('S_mm', 'le', 50, 'mm')])
    assert result['passed'] is True


def test_review_fails():
    events = [{'result': {'ok': True, 'metrics': {'S_mm': {'value': 70, 'unit': 'mm'}}}}]
    result = review(events, [_c('S_mm', 'le', 50, 'mm')])
    assert result['passed'] is False


# ---------------------------------------------------------------------------
# tools._truncate_result
# ---------------------------------------------------------------------------

def test_truncate_small_result_unchanged():
    r = {'ok': True, 'data': 'x' * 100}
    assert _truncate_result(r) == r


def test_truncate_large_result():
    r = {'ok': True, 'data': 'x' * 3000, 'metrics': {'S_mm': 30}}
    out = _truncate_result(r)
    assert out.get('_truncated') is True
    assert out['ok'] is True
    assert 'metrics' in out


def test_descriptions_compact():
    for name, desc in DESCRIPTIONS.items():
        assert len(desc) <= 300, f'{name} description too long: {len(desc)} chars'


# ---------------------------------------------------------------------------
# project_memory._compact_event
# ---------------------------------------------------------------------------

def test_compact_event_keeps_ok_flag():
    event = {'tool': 'plaxis_safe_inspect', 'arguments': {}, 'result': {'ok': True, 'data': 'x' * 5000}}
    c = _compact_event(event)
    assert c['result']['ok'] is True
    assert 'data' not in c['result']


def test_compact_event_keeps_metrics():
    event = {'tool': 'plaxis_safe_geo_calculate', 'result': {'ok': True, 'metrics': {'S_mm': 42}}}
    c = _compact_event(event)
    assert c['result']['metrics'] == {'S_mm': 42}


def test_max_events_is_compact():
    assert _MAX_EVENTS <= 5, 'MAX_EVENTS should stay small to limit context'


# ---------------------------------------------------------------------------
# agent.SYSTEM — static (no dynamic content)
# ---------------------------------------------------------------------------

def test_system_prompt_static():
    assert '{' not in SYSTEM, 'system prompt must not contain format placeholders'


def test_system_prompt_length():
    assert len(SYSTEM) <= 700, f'System prompt too long: {len(SYSTEM)} chars (raises input token cost)'


# ---------------------------------------------------------------------------
# agent._build_human_message — compact context
# ---------------------------------------------------------------------------

def test_human_message_includes_version():
    msg = _build_human_message('test', '2d', [], None)
    assert '2d' in msg.content


def test_human_message_truncates_large_context():
    big_ctx = {'data': 'x' * 5000}
    msg = _build_human_message('test', '2d', [], big_ctx)
    assert len(msg.content) < 2000, 'human message should be compact'
    assert 'cắt' in msg.content or 'inspect' in msg.content


def test_human_message_no_context():
    msg = _build_human_message('prompt', '3d', [], None)
    assert 'Lịch sử' not in msg.content
