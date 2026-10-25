import json
from collections import Counter
from pathlib import Path


def test_release_is_diagnostics_and_never_claims_returns_or_execution():
    report = json.loads((Path(__file__).resolve().parents[1] /
                         'web/public/strategy/weekly-v1.2.json').read_text(encoding='utf-8'))
    assert report['version'] == 'cn-weekly-pullback-v1.2'
    assert report['returns_computed'] is False
    assert report['execution_ready'] is False
    assert report['automation_enabled'] is False
    assert report['full_strategy_eligible'] == 0
    assert len(set(report['universe'])) == report['stocks'] == 28
    assert Counter(e['stage'] for e in report['events']) == {'pullback': 32, 'observe': 4, 'confirmed': 1}
    for event in report['events']:
        assert not event['eligible']
        assert event['score_max'] == 85
        assert event['components']['sector']['points'] is None
        assert not event['preview']['execution_ready']
    case = next(e for e in report['events'] if e['stage'] == 'confirmed')
    assert case['code'] == 'sh.600546'
    assert case['entry_risk']['price_risk_passed'] is False
    assert len(case['entry_risk']['reasons']) == 2
