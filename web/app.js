// 광명 임대주택 공고 목록. data/notices.json을 읽어 그린다.
// - 접수 상태는 저장하지 않고 오늘 날짜(한국 시간)로 계산
// - 외부에서 온 글은 textContent로만 넣는다 (innerHTML 사용 안 함)
"use strict";

const SOURCE_NAMES = { lh: "LH", gh: "GH", gm_corp: "광명도시공사", gm_city: "광명시청", myhome: "마이홈" };
const WEEKDAYS = "일월화수목금토";
const URGENT_DAYS = 3;
const YOUNG_ONLY = "청년·신혼 등 대상";
const STALE_HOURS = 30; // 마지막 확인이 이보다 오래되면 경고 표시
const UNSURE_TAGS = ["광명 포함 여부 확인 필요", "광역 공고"]; // 광명 확정이 아닌 표시
const DEMO = new URLSearchParams(location.search).has("demo");
// 유형 목록은 지금 공고가 없어도 항상 보여준다 (부모님께 익숙한 순서)
const HOUSING_TYPES = ["영구임대", "국민임대", "행복주택", "매입임대", "통합공공임대", "전세임대", "장기전세"];
// 보증금 + 매달 임대료를 내는 유형
const MONTHLY_TYPES = ["영구임대", "국민임대", "행복주택", "매입임대", "통합공공임대", "공공임대", "50년임대", "10년임대"];

let notices = [];

// 한국 시간 오늘 날짜 (YYYY-MM-DD)
function todayKST() {
  return new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
}

function daysBetween(a, b) {
  return Math.round((Date.parse(b) - Date.parse(a)) / 86400e3);
}

// 접수기간 문구: 시작·마감 중 하나만 알 때도 자연스럽게
function fmtPeriod(start, end) {
  if (start && end) return `${fmtDate(start)} ~ ${fmtDate(end)}`;
  if (end) return `~ ${fmtDate(end)}까지`;
  if (start) return `${fmtDate(start)}부터`;
  return "공고문 확인";
}

function fmtDate(iso) {
  if (!iso) return "?";
  const d = new Date(iso + "T00:00:00Z");
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()}(${WEEKDAYS[d.getUTCDay()]})`;
}

function status(n, today) {
  const start = n.apply_start, end = n.apply_end;
  if (!start && !end) return { key: "unknown", label: "일정 공고문 확인" };
  if (end && today > end) return { key: "closed", label: "마감" };
  if (start && today < start) return { key: "soon", label: "접수예정" };
  const left = end ? daysBetween(today, end) : null;
  return { key: "open", label: "접수중", left };
}

// 월세형/전세형. "든든전세"·"매입임대Ⅱ(전세형)"처럼 제목에 전세가 있으면 전세형
function rentKind(n) {
  const text = `${n.housing_type || ""} ${n.title || ""}`;
  if (/전세/.test(text)) return "전세형";
  if (MONTHLY_TYPES.some((t) => text.includes(t))) return "월세형";
  return null;
}

// 광명 확정: "확인 필요"·"광역" 표시가 없고, 광명 기관 공고이거나 지역·주소에 광명이 있음
function isGwangmyeong(n) {
  if ((n.tags || []).some((t) => UNSURE_TAGS.some((u) => t.startsWith(u)))) return false;
  if (n.source === "gm_city" || n.source === "gm_corp") return true;
  return /광명/.test(`${n.region || ""} ${n.address || ""}`);
}

// ?demo=1 일 때만 보이는 테스트 공고 (실제 데이터·알림과 무관)
function demoNotices(today) {
  const day = (d) => new Date(Date.parse(today) + d * 86400e3).toISOString().slice(0, 10);
  const base = { url: location.href.split("?")[0], institution: "테스트", tags: [], alert_reason: null };
  return [
    { ...base, key: "demo:1", source: "gm_city", title: "[테스트] 광명하안 영구임대주택 예비입주자 모집 (접수중·광명 확정)",
      posted_at: day(-3), apply_start: day(-1), apply_end: day(10), region: "경기도 광명시 하안동",
      address: "경기도 광명시 하안로 60", map_url: null, housing_type: "영구임대", target: "고령자, 수급자",
      summary: "테스트용 카드입니다", apply_method: "신청장소: 주민등록지 행정복지센터", tags: ["고령자 해당 가능"] },
    { ...base, key: "demo:2", source: "gm_corp", title: "[테스트] 광명소하 행복주택 입주자 모집 (접수예정·광명 확정)",
      posted_at: day(-1), apply_start: day(5), apply_end: day(7), region: "경기도 광명시", housing_type: "행복주택" },
    { ...base, key: "demo:3", source: "lh", title: "[테스트] [경기남부] 매입임대주택 입주자 모집 (접수중·광명 불확실 → 기본 색)",
      posted_at: day(-2), apply_start: day(-1), apply_end: day(2), region: "경기도", housing_type: "매입임대",
      tags: ["광명 포함 여부 확인 필요"] },
    { ...base, key: "demo:4", source: "gm_city", title: "[테스트] 광명 국민임대 예비입주자 모집 (마감·광명 → 기본 색)",
      posted_at: day(-20), apply_start: day(-15), apply_end: day(-10), region: "경기도 광명시", housing_type: "국민임대" },
  ];
}

function safeUrl(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch { return null; }
}

function el(tag, text, cls) {
  const e = document.createElement(tag);
  if (text != null) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

function badge(text, cls) { return el("span", text, "badge " + cls); }

function link(text, url, secondary) {
  const href = safeUrl(url);
  if (!href) return null;
  const a = el("a", text, secondary ? "secondary" : "");
  a.href = href;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  return a;
}

function section(title, text) {
  if (!text) return [];
  return [el("h3", title), el("p", text)];
}

function buildDetail(n) {
  const box = document.createDocumentFragment();
  const content = [n.summary || n.housing_type, n.target && `대상: ${n.target}`].filter(Boolean).join("\n");
  [
    ...section("내용", content),
    ...section("공고일", n.posted_at && fmtDate(n.posted_at)),
    ...section("접수기간", fmtPeriod(n.apply_start, n.apply_end)),
    ...section("신청방법", n.apply_method),
    ...section("공급기관", n.institution),
  ].forEach((e) => box.append(e));

  // 첨부: 바로 받을 수 있는 링크만 걸고, 나머지는 이름만 (원문에서 받기)
  if (n.attachments && n.attachments.length) {
    box.append(el("h3", "첨부 공고문"));
    const ul = el("ul", null, "files");
    n.attachments.forEach((f) => {
      const li = el("li");
      const direct = !f.form && f.kind !== "공고문" && safeUrl(f.url);
      const a = direct ? link(f.name || "첨부파일", f.url) : null;
      li.append(a || el("span", f.name || "첨부파일"));
      ul.append(li);
    });
    box.append(ul, el("p", "링크가 없는 파일은 공고 원문 페이지에서 받으세요.", "note"));
  }

  const links = el("div", null, "links");
  [
    link("공고 원문 보기", n.url),
    link("지도 보기", n.map_url, true),
    n.source === "gm_corp" ? link("광명도시공사 청약센터", "https://house.gmuc.co.kr/?menu=notice", true) : null,
  ].filter(Boolean).forEach((a) => links.append(a));
  box.append(links);
  return box;
}

function render() {
  const today = todayKST();
  const onlyOpen = document.getElementById("f-open").checked;
  const hideYoung = document.getElementById("f-hide-young").checked;
  const source = document.getElementById("f-source").value;
  const type = document.getElementById("f-type").value;
  const rent = document.getElementById("f-rent").value;
  const q = document.getElementById("f-q").value.trim().toLowerCase();

  const shown = notices.filter((n) => {
    const st = status(n, today);
    if (n.duplicate_of) return false;
    if (onlyOpen && !(st.key === "open" || st.key === "soon")) return false;
    if (hideYoung && n.alert_reason === YOUNG_ONLY) return false;
    if (source && n.source !== source) return false;
    if (type && n.housing_type !== type) return false;
    if (rent && rentKind(n) !== rent) return false;
    if (q) {
      const hay = [n.title, n.region, n.summary, n.housing_type, n.institution, n.target]
        .filter(Boolean).join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const list = document.getElementById("list");
  list.replaceChildren();
  document.getElementById("count").textContent = `공고 ${shown.length}건`;
  if (!shown.length) {
    list.append(el("p", "조건에 맞는 공고가 없습니다.", "empty"));
    return;
  }

  const tpl = document.getElementById("card-tpl");
  shown.forEach((n) => {
    const card = tpl.content.firstElementChild.cloneNode(true);
    const st = status(n, today);
    const urgent = st.key === "open" && st.left != null && st.left <= URGENT_DAYS;
    if (urgent) card.classList.add("urgent");
    if (st.key === "closed") card.classList.add("closed");
    const gmOpen = (st.key === "open" || st.key === "soon") && isGwangmyeong(n);
    if (gmOpen) card.classList.add("gm-open");

    const badges = card.querySelector(".badges");
    badges.append(badge(st.label, "status-" + st.key));
    if (urgent) badges.append(badge(st.left === 0 ? "오늘 마감" : `마감 D-${st.left}`, "urgent"));
    if (gmOpen) badges.append(badge("광명", "gm"));
    const kind = rentKind(n);
    if (kind) badges.append(badge(kind, kind === "월세형" ? "monthly" : "jeonse"));
    badges.append(badge(SOURCE_NAMES[n.source] || n.institution || "공고", "source"));
    (n.tags || []).forEach((t) => badges.append(badge(t, t.includes("고령자") ? "senior" : "tag")));

    card.querySelector(".title").textContent = n.title;
    card.querySelector(".region").textContent = "📍 " + (n.region || "지역 공고문 확인");
    card.querySelector(".period").textContent = "⏰ 접수 " + fmtPeriod(n.apply_start, n.apply_end);

    const head = card.querySelector(".head");
    const detail = card.querySelector(".detail");
    head.addEventListener("click", () => {
      const open = detail.hidden;
      if (open && !detail.childNodes.length) detail.append(buildDetail(n));
      detail.hidden = !open;
      head.setAttribute("aria-expanded", String(open));
    });
    list.append(card);
  });
}

function fillOptions(id, values, labels = {}, order = []) {
  const sel = document.getElementById(id);
  const rank = (v) => (order.includes(v) ? order.indexOf(v) : order.length);
  [...new Set(values.filter(Boolean))].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b)).forEach((v) => {
    const o = el("option", labels[v] || v);
    o.value = v;
    sel.append(o);
  });
}

function showUpdated(checkedAt, updatedAt) {
  const p = document.getElementById("updated");
  const when = checkedAt || updatedAt;
  if (!when) { p.textContent = ""; return; }
  const d = new Date(when);
  const hours = (Date.now() - d.getTime()) / 3600e3;
  const text = d.toLocaleString("ko-KR", { timeZone: "Asia/Seoul", month: "numeric", day: "numeric",
    weekday: "short", hour: "numeric", minute: "2-digit" });
  p.textContent = `마지막 확인: ${text}`;
  if (hours > STALE_HOURS) {
    p.textContent += " (수집이 멈췄을 수 있어요)";
    p.classList.add("stale");
  }
}

async function main() {
  try {
    const [data, st] = await Promise.all([
      fetch("data/notices.json", { cache: "no-store" }).then((r) => r.json()),
      fetch("data/status.json", { cache: "no-store" }).then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
    ]);
    if (DEMO) {
      data.notices = demoNotices(todayKST()).concat(data.notices || []);
      document.getElementById("demo").hidden = false;
    }
    notices = (data.notices || []).slice().sort((a, b) =>
      (b.posted_at || "").localeCompare(a.posted_at || ""));
    showUpdated(st.checked_at, data.updated_at);
    fillOptions("f-source", notices.map((n) => n.source), SOURCE_NAMES);
    fillOptions("f-type", HOUSING_TYPES.concat(notices.map((n) => n.housing_type)), {}, HOUSING_TYPES);
  } catch (e) {
    document.getElementById("updated").textContent = "공고 목록을 불러오지 못했습니다. 잠시 후 다시 열어 주세요.";
    return;
  }
  ["f-open", "f-hide-young", "f-source", "f-type", "f-rent"].forEach((id) =>
    document.getElementById(id).addEventListener("change", render));
  document.getElementById("f-q").addEventListener("input", render);
  render();
}

main();
