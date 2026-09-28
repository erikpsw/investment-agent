from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "market-snapshot.yml"


def test_market_snapshot_workflow_stages_generated_market_directory():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "update_market_snapshot.mjs").read_text(encoding="utf-8")
    assert "git add -A storage/market" in workflow
    assert '"hot-hk.json"' in script
    assert '"hot-us.json"' in script
