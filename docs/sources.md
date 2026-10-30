# 소스 조사 결과 (단계 1)

조사일: 2026-10-30. **[V]** 직접 호출·접속해서 확인, **[D]** 공식 문서로만 확인(실제 응답 미확인), **[I]** 추론.

## 1. 요약과 수집 구성

| 소스 | 수집 방식 | 광명 필터 | 역할 |
|---|---|---|---|
| 마이홈포털 | 공식 API (data.go.kr) | 서버에서 (`brtcCode=41&signguCode=210`) | **메인.** LH·광명도시공사 공고 포함 |
| LH | 공식 API (data.go.kr) | 시도까지만 → 수집 후 | 마이홈에 들어온 LH 공고의 **상세 보강**(접수처, 일정, 대상, 신청방법) |
| GH | HTML 크롤링 (apply.gh.or.kr) | 서버에서 (`searchArea=4121`) + 수집 후 | **별도 수집 필수.** 마이홈에 GH 공고가 거의 없음 |
| 광명도시공사 | 마이홈 API로 커버. house.gmuc.co.kr은 보강용 | 불필요 (전부 광명) | 마이홈에 없는 건/첨부파일 보강 |
| 광명시청 | HTML 크롤링 (고시공고·공지사항) | 제목 검색 + 제외어 | 전세임대·매입임대 등 다른 곳에 안 잡히는 공고 보완 |

중복 처리: 같은 공고가 여러 소스에 나온다(시청이 LH/GH/도시공사 공고를 재게시 등). `key`로 소스 내 중복을 막고, 소스 간에는 제목 정규화 + 공고일 근접으로 묶는다.

## 2. 마이홈포털 — 공공주택 모집공고 조회 서비스

- data.go.kr: https://www.data.go.kr/data/15108420/openapi.do [V]
- 엔드포인트: `https://apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList` (공공임대) [V]
- JSON, 개발계정 1,000건/일, 자동승인, 무료 [V]
- 파라미터: `serviceKey`, `brtcCode`, `signguCode`, `numOfRows`, `pageNo`, `suplyTy`, `houseTy`, `yearMtBegin`/`yearMtEnd`(YYYYMM) [V]
- 광명시: `brtcCode=41`, `signguCode=210` (공식 코드 엑셀) [V]. 2026년 1~10월 광명 22건(LH 19, 광명도시공사 3) [V, 웹 목록]
- 광역 공고("[경기남부] 매입임대" 등)도 섞여 나옴 → 그대로 포함하되 지역 표기를 "경기 남부권(광명 포함)"처럼 원문대로

| 알림 항목 | 필드 [D] |
|---|---|
| 공고명 | `pblancNm` |
| 공고일 | `rcritPblancDe` |
| 접수기간 | `beginDe` ~ `endDe` |
| 지역 | `brtcNm` `signguNm` (`refrnLegaldongNm`) |
| 주소 | `fullAdres`, `hsmpNm`(단지명) |
| 공급유형 | `suplyTyNm`, `houseTyNm` |
| 세대수 | `totHshldCo`, `sumSuplyCo` |
| 신청방법 | **없음** (`refrnc` 문의처만) → LH 상세 API / 첨부 AI 추출 |
| 대상 | **없음** → 동일 |
| 원문 URL | `url`, `pcUrl` |
| 고유 ID | `pblancId` (정정공고: `beforePblancId`) |
| 기관 | `suplyInsttNm` (LH / 광명도시공사 …) |

**실제 호출 결과 (2026-10-30) [V]** — 샘플: `tests/fixtures/myhome_gyeonggi.json`, `myhome_gwangmyeong.json`
- **현재 진행 중인 공고만 반환.** `yearMtBegin/End`를 줘도 결과가 같거나(경기 17건) 과거 월만 주면 `NODATA_ERROR`(resultCode 03) → 과거 공고 일괄 수집 불가, seed는 "지금 진행 중인 것"만
- 광명(`signguCode=210`) 현재 0건 → `resultCode 03`은 오류가 아니라 "0건"으로 처리
- **한 공고가 단지(`houseSn`)별로 여러 줄** (화성 동탄 1건이 8줄) → `key = myhome:{pblancId}`로 묶고 단지 목록은 합침
- **전세임대 수시모집 같은 광역 공고는 `signguNm`이 비어 있음** → `signguCode=210` 필터에 안 걸림. `brtcCode=41`로 받고 코드에서 판정해야 함
- 날짜는 `YYYYMMDD` 문자열, 금액은 숫자(`rentGtn` 보증금, `mtRntchrg` 월임대료), `url`은 LH 원문(panId 포함), `pcUrl`은 마이홈 상세
- 응답 `body.item`은 리스트

- GH 커버리지: 2026년 8~10월 경기 77건 중 GH 0건 [V] → GH 별도 수집
- 웹 목록 AJAX(`/hws/portal/sch/selectRsdtRcritNtcList.do`)는 비공식·대기열 있음 → 사용 안 함

## 3. LH — 분양임대공고 API (보강용)

- 목록: https://www.data.go.kr/data/15058530/openapi.do → `https://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1` [V]
- 상세: https://www.data.go.kr/data/15057999/openapi.do → `https://apis.data.go.kr/B552555/lhLeaseNoticeDtlInfo1/getLeaseNoticeDtlInfo1` [V]
- (선택) 공급정보: https://www.data.go.kr/data/15056765/openapi.do (주택형별 세대수·임대료)
- JSON, 10,000건/일, 자동승인 [V]
- 목록 필터: `UPP_AIS_TP_CD`(06 임대주택, 13 주거복지), `CNP_CD=41`(시도까지만) → 광명은 수집 후 판정 [V]
- 상세 응답 [D]: 접수처 `dsCtrtPlc`, 단지 주소 `dsSbd`(`LGDN_ADR`), 접수기간 `dsSplScdl`(`SBSC_ACP_ST_DT`/`SBSC_ACP_CLSG_DT` 등 유형별 상이), 신청방법 `RMK`, 대상 `dsEtcList`, 첨부 `AHFL_URL`
- 마이홈 `url`의 `panId`로 LH 공고와 연결

**실제 호출 결과 (2026-10-30) [V]** — 샘플: `tests/fixtures/lh_list_gyeonggi.json`, `lh_detail_sample.json`
- 목록: `[{"dsSch":[…]}, {"resHeader":[…], "dsList":[…]}]`. 경기 임대 19건, **마감된 공고도 포함**(최근 약 2개월). 날짜 `YYYY.MM.DD`, `PAN_DT`만 `YYYYMMDD`
- 목록 행에 상세 호출 키(`SPL_INF_TP_CD`, `CCR_CNNT_SYS_DS_CD`, `UPP_AIS_TP_CD`, `AIS_TP_CD`)가 모두 있음 → 바로 상세 호출 가능
- 상세: `dsSplScdl`(접수 `SBSC_ACP_ST_DT`~`SBSC_ACP_CLSG_DT`, 당첨발표 `PZWR_ANC_DT`), `dsSbd`(주소 `LGDN_ADR`+`LGDN_DTL_ADR` → "경기도 과천시 갈현동 581-1", 세대수 `HSH_CNT`), `dsEtcInfo.ETC_CTS`(신청방법 안내 문장), `dsAhflInfo`(공고문 링크)
- `dsSbdNm`, `dsSbdAhflNm`처럼 `…Nm` 데이터셋은 **컬럼 이름표**(값 아님) → 무시
- 첨부 링크는 모두 `lhFile.do`(robots 금지) → 링크만 표시
- **apply.lh.or.kr robots.txt가 첨부 다운로드(`/lhapply/lhFile.do`)를 금지** [V] → LH 공고문 파일은 자동으로 내려받지 않고 링크만 제공. LH는 상세 API의 구조화 필드로 충분

## 4. GH — 청약센터 apply.gh.or.kr

- `www.gh.or.kr` robots.txt: `Disallow: /` (전체 금지) → **사용 안 함** [V]
- `apply.gh.or.kr` robots.txt: `Allow: /*` [V]. 서버 렌더링 HTML, 로그인 불필요 [V]
- 임대 목록: `https://apply.gh.or.kr/sb/sr/sr7150/selectPbancRentHouseList.do?searchArea=4121&pageIndex=N` [V]
- 매입임대 목록: `.../sr7155/selectPbancRentHouseList.do` (지역이 "경기도"로만 표기됨 → 본문에서 광명 판정) [V]
- 상세: `.../sr7150/selectPbancDetailView.do?pbancNo=N&pbancKndCd=01&previewYn=N` [V]
  - 공고명, 유형, 공고일, 소재지(전체 주소), 모집호수, 접수기간(온라인/현장), 접수처, 공고문 첨부
- 고유 ID: `pbancNo`. 첨부: `apply-cdn.gh.or.kr/.../selectFileDown.do` [V]
- 다지역 공고("(의정부·안양·광명·안산) 장기전세")는 지역 필터에 안 걸림 → 전체 목록도 받아서 제목·본문의 "광명"으로 추가 판정 [V]

## 5. 광명도시공사 — house.gmuc.co.kr

- 임대주택 청약센터. 로그인 불필요, robots.txt 없음 [V]
- 목록: `POST /jsp/guser/notice_list.jsp` (`pagenum`, `Type`, `Noticename`) → HTML 조각 [V]
- 상세: `POST /jsp/guser/notice_view.jsp` (`Noticeid`) → 공고별 고정 URL 없음 [V]
- 목록에 날짜 없음, 후속 글(서류제출 대상자, 추첨결과)이 섞임 → 제목에 "모집"인 글만 [V]
- 마이홈 API가 광명도시공사 공고를 포함하므로 **기본은 마이홈으로 수집**, 이 사이트는 첨부 공고문(AI 추출용)과 누락 보완용
- 메인 사이트 www.gmuc.co.kr 게시판은 Googlebot에 `/user/board/` 금지 → 사용 안 함

## 6. 광명시청 — gm.go.kr

- robots.txt: `*`는 `/intra/`만 금지 [V]. 서버 렌더링, 로그인 불필요, RSS 없음 [V]
- 고시공고: `https://www.gm.go.kr/pt/user/nftcBbs/BD_selectNftcBbsList.do?q_nftcBbsCode=1001&q_searchKeyTy=1001&q_searchVal={UTF-8 인코딩}` [V]
  - 상세: `BD_selectNftcBbsDetail.do?q_nftcBbsCode=1001&q_nftcBbsMgtno={id}`
  - 첨부: `eminwon.gm.go.kr` POST, **응답이 자주 끊김** → 재시도·다음 실행으로 미룸
- 공지사항: `https://www.gm.go.kr/pt/user/bbs/BD_selectBbsList.do?q_bbsCode=2032&q_searchKeyTy=sj___1002&q_searchVal={…}` [V]
  - 상세: `BD_selectBbs.do?q_bbsCode=2032&q_bbscttSn={id}`. 상단 고정 "공지" 2건 제외
- 양: 고시공고 월 250~340건 중 실제 임대 모집공고는 **연 6건 안팎**, 공지사항은 월 0.5~1건 [V]
- 검색어: 임대, 입주자, 행복주택, 매입임대, 전세임대, 예비입주
- 제외어: 공시송달, 과태료, 임대차계약, 매각, 사무실, 오피스, 채용, 창업
- 접수기간·신청방법은 본문 자유 텍스트 또는 첨부에만 있음 → 정규식 + 첨부 AI 추출

## 7. 첨부 공고문 AI 추출

- 모델: `claude-haiku-5-5` (사용자 선택, config.yaml에서 변경 가능)
- 대상: GH, 광명도시공사, 광명시청 첨부 (LH는 robots.txt로 제외)
- 형식 판별은 확장자가 아닌 파일 내용으로 (`.hwpx`인데 HWP5인 파일 확인됨 [V])
- PDF → Claude API 문서 입력, HWPX → XML 텍스트, HWP5 → olefile로 본문 텍스트, 배포용(암호) HWP → "공고문 확인"
- 각 항목에 근거 문장을 받고 원문에 실제로 있는지 코드로 검증, 없으면 버림

## 8. 미확인 (API 키 발급 후 확인)

- 마이홈·LH API 실제 응답 본문, `url` 값이 채워지는지, `numOfRows` 최대값
- LH 목록 날짜 파라미터의 실제 이름/형식 (문서마다 다름)
- 경기데이터드림의 GH 공고 API (키 필요) — 크롤링 대신 쓸 수 있는지
