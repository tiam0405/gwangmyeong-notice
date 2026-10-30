"""한 번 실행 = 수집 → 필터 → 신규 저장 → 알림 → 리마인더.

    python main.py          # 일반 실행
    python main.py --seed   # 첫 실행: 알림 없이 저장만
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import fields
from pathlib import Path

import yaml
from dotenv import load_dotenv

from collectors.base import BaseCollector
from collectors.gh import GHCollector
from collectors.gm_city import GmCityCollector
from collectors.gm_corp import GmCorpCollector
from collectors.lh import LHCollector
from collectors.myhome import MyHomeCollector
from dedupe import SOURCE_PRIORITY, by_priority, find_duplicate
from enrich.geocode import map_url
from filters import classify, is_correction
from models import Notice
from store import Store, today_kst

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


def merge_notices(notices: list[Notice]) -> list[Notice]:
    """같은 key(예: 마이홈과 LH에 모두 있는 LH 공고)를 하나로 합친다.

    먼저 수집된 쪽 값을 우선하고, 비어 있는 칸만 뒤쪽 값으로 채운다.
    """
    merged: dict[str, Notice] = {}
    for n in notices:
        base = merged.get(n.key)
        if base is None:
            merged[n.key] = n
            continue
        for f in fields(Notice):
            if f.name == "raw":
                continue
            if not getattr(base, f.name) and getattr(n, f.name):
                setattr(base, f.name, getattr(n, f.name))
        for k, v in n.raw.items():
            if not base.raw.get(k):
                base.raw[k] = v
    return list(merged.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="알림 없이 저장만")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    setup_logging()
    config = load_config()

    notices = merge_notices(collect(config))
    log.info("총 %d건 수집 (seed=%s)", len(notices), args.seed)

    store = Store(ROOT / "data" / "notices.json")
    today = today_kst()
    process(notices, store, config, today, seed=args.seed)
    # TODO 단계 5~10: 지도 링크·신청방법 보강 → 알림 → 리마인더
    store.archive_old(today)
    store.save()


def process(notices: list[Notice], store: Store, config: dict, today, seed: bool = False) -> None:
    """판정 → 중복 확인 → 저장. 알림 대상 여부는 레코드의 alert로 남긴다."""
    seen = [{"key": r["key"], "source": r["source"], "title": r["title"], "posted_at": r["posted_at"]}
            for r in store.records.values()]
    # 원 기관 공고가 먼저, 같은 소스에서는 원공고가 정정공고보다 먼저
    ordered = sorted(by_priority(notices), key=lambda n: (SOURCE_PRIORITY.get(n.source, 9),
                                                           is_correction(n.title)))
    kept = new = 0
    for notice in ordered:
        verdict = classify(notice, config, today)
        if not verdict.keep:
            log.debug("제외 (%s): %s", verdict.reason, notice.title)
            continue
        extra = {"map_url": map_url(notice.address)}
        if (dup := find_duplicate(notice, seen)):
            extra["duplicate_of"] = dup
            if verdict.alert:
                verdict.alert, verdict.reason = False, f"중복 ({dup}와 같은 공고)"
        seen.append({"key": notice.key, "source": notice.source, "title": notice.title,
                     "posted_at": notice.posted_at})
        kept += 1
        _, is_new = store.upsert(notice, alert=verdict.alert, tags=verdict.tags, **extra)
        if is_new:
            new += 1
            log.info("신규%s: %s", "" if verdict.alert else f" (알림 제외: {verdict.reason})", notice.title)
            if seed:
                store.mark_notified(notice.key, seeded=True)
    log.info("광명 대상 %d건, 신규 %d건", kept, new)


if __name__ == "__main__":
    main()
