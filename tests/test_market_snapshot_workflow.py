import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "market-snapshot.yml"


def test_market_snapshot_workflow_only_stages_existing_outputs():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    staged_paths = set(re.findall(r"storage/market/[a-z0-9-]+\.json", workflow))

    assert staged_paths
    missing = sorted(path for path in staged_paths if not (ROOT / path).is_file())
    assert missing == [], f"workflow stages files that are never generated: {missing}"
