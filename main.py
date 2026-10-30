"""한 번 실행 = 수집 → 필터 → 신규 저장 → 알림 → 리마인더.

    python main.py          # 일반 실행
    python main.py --seed   # 첫 실행: 알림 없이 저장만
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from collectors.base import BaseCollector
from collectors.gh import GHCollector
from collectors.gm_city import GmCityCollector
from collectors.gm_corp import GmCorpCollector
from collectors.lh import LHCollector
from collectors.myhome import MyHomeCollector

ROOT = Path(__file__).parent
COLLECTORS: dict[str, type[BaseCollector]] = {
    "myhome": MyHomeCollector,
    "lh": LHCollector,
    "gh": GHCollector,
    "gm_city": GmCityCollector,
    "gm_corp": GmCorpCollector,
}

log = logging.getLogger("main")


def load_config(path: Path = ROOT / "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 한글 깨짐 방지
    sys.stderr.reconfigure(encoding="utf-8")
    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(ROOT / "logs" / "run.log", encoding="utf-8"),
        ],
    )


def collect(config: dict) -> list:
    """활성화된 수집기를 모두 돌린다. 한 소스가 실패해도 나머지는 계속."""
    notices = []
    for name, cls in COLLECTORS.items():
        if not config["sources"].get(name, {}).get("enabled"):
            continue
        try:
            found = cls(config).fetch()
            log.info("%s: %d건", name, len(found))
            notices.extend(found)
        except NotImplementedError:
            log.info("%s: 아직 구현되지 않음", name)
        except Exception:
            log.exception("%s 수집 실패", name)
    return notices


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="알림 없이 저장만")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    setup_logging()
    config = load_config()

    notices = collect(config)
    log.info("총 %d건 수집 (seed=%s)", len(notices), args.seed)
    # TODO 단계 3~10: 필터 → store 저장 → 알림 → 리마인더


if __name__ == "__main__":
    main()
