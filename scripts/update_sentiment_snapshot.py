"""Generate and persist storage/market/sentiment.json from live providers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from investment.data.market_sentiment import refresh_sentiment_snapshot  # noqa: E402


def main() -> None:
    payload = refresh_sentiment_snapshot()
    print(f"Sentiment snapshot ready at {payload['generated_at']}")
    for market in payload.get("markets", []):
        resonance = market.get("resonance") or {}
        print(
            f"  {market['market']} ({market['name']}): "
            f"score={market['score']} [{market['label']}] "
            f"pos={market['position_range']} "
            f"resonance={resonance.get('signal')} ({resonance.get('trigger_count', 0)})"
        )


if __name__ == "__main__":
    main()
