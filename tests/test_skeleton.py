import json
from pathlib import Path

import main

ROOT = Path(__file__).parent.parent


def test_config_loads():
    config = main.load_config()
    assert set(config["sources"]) == set(main.COLLECTORS)
    assert "광명" in config["filters"]["region_keywords"]


def test_notices_json_is_valid():
    data = json.loads((ROOT / "data" / "notices.json").read_text(encoding="utf-8"))
    assert data["notices"] == []


def test_no_secrets_in_tracked_config():
    text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    for name in ("DATA_GO_KR_KEY=", "ANTHROPIC_API_KEY=", "TELEGRAM_BOT_TOKEN="):
        assert name not in text
