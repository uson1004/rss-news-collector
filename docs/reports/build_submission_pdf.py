from __future__ import annotations

import json
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output" / "pdf" / "3208_윤유섭_프로젝트보고서_읽을게.pdf"
DATA_PATH = ROOT / "exports" / "presentation-data.json"
NEWS_IMAGE = ROOT / "tmp" / "pdfs" / "submission-report" / "news-screen-crop.png"
URL_IMAGE = ROOT / "tmp" / "pdfs" / "submission-report" / "url-screen-crop.png"

SERIF_FONT = "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf"
SANS_FONT = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"

NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2F5597")
LIGHT_BLUE = colors.HexColor("#D9EAF7")
PALE_BLUE = colors.HexColor("#EEF4FA")
LIGHT_GRAY = colors.HexColor("#F3F5F7")
MID_GRAY = colors.HexColor("#666666")
DARK = colors.HexColor("#222222")
LINE = colors.HexColor("#B4C6E7")
RED = colors.HexColor("#A92D20")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("KoreanSerif", SERIF_FONT))
    pdfmetrics.registerFont(TTFont("KoreanSans", SANS_FONT))
    pdfmetrics.registerFontFamily(
        "KoreanSerif",
        normal="KoreanSerif",
        bold="KoreanSans",
        italic="KoreanSerif",
        boldItalic="KoreanSans",
    )
    pdfmetrics.registerFontFamily(
        "KoreanSans",
        normal="KoreanSans",
        bold="KoreanSans",
        italic="KoreanSans",
        boldItalic="KoreanSans",
    )


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Normal"],
            fontName="KoreanSans",
            fontSize=25,
            leading=31,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=5 * mm,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="KoreanSans",
            fontSize=13,
            leading=18,
            textColor=MID_GRAY,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "kicker": ParagraphStyle(
            "Kicker",
            parent=base["Normal"],
            fontName="KoreanSans",
            fontSize=9.5,
            leading=13,
            textColor=BLUE,
            alignment=TA_CENTER,
            spaceAfter=2 * mm,
        ),
        "h1": ParagraphStyle(
            "Heading1",
            parent=base["Normal"],
            fontName="KoreanSans",
            fontSize=15,
            leading=21,
            textColor=NAVY,
            spaceBefore=1 * mm,
            spaceAfter=2.5 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=base["Normal"],
            fontName="KoreanSans",
            fontSize=12.5,
            leading=17,
            textColor=BLUE,
            spaceBefore=2.5 * mm,
            spaceAfter=1.3 * mm,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "Heading3",
            parent=base["Normal"],
            fontName="KoreanSans",
            fontSize=10.5,
            leading=15,
            textColor=NAVY,
            spaceBefore=1.5 * mm,
            spaceAfter=1 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="KoreanSerif",
            fontSize=10,
            leading=16,
            textColor=DARK,
            alignment=TA_JUSTIFY,
            wordWrap="CJK",
            spaceAfter=2.2 * mm,
        ),
        "body_tight": ParagraphStyle(
            "BodyTight",
            parent=base["Normal"],
            fontName="KoreanSerif",
            fontSize=10,
            leading=15.5,
            textColor=DARK,
            alignment=TA_JUSTIFY,
            wordWrap="CJK",
            spaceAfter=1.5 * mm,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["Normal"],
            fontName="KoreanSerif",
            fontSize=10,
            leading=16,
            textColor=DARK,
            leftIndent=6 * mm,
            firstLineIndent=-3.5 * mm,
            bulletIndent=0,
            wordWrap="CJK",
            spaceAfter=1.2 * mm,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontName="KoreanSerif",
            fontSize=8.4,
            leading=12,
            textColor=DARK,
            wordWrap="CJK",
        ),
        "small_center": ParagraphStyle(
            "SmallCenter",
            parent=base["Normal"],
            fontName="KoreanSerif",
            fontSize=8.4,
            leading=12,
            textColor=DARK,
            alignment=TA_CENTER,
            wordWrap="CJK",
        ),
        "small_bold": ParagraphStyle(
            "SmallBold",
            parent=base["Normal"],
            fontName="KoreanSans",
            fontSize=8.5,
            leading=12,
            textColor=NAVY,
            wordWrap="CJK",
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["Normal"],
            fontName="KoreanSerif",
            fontSize=8.5,
            leading=12,
            textColor=MID_GRAY,
            alignment=TA_CENTER,
            spaceBefore=1 * mm,
            spaceAfter=2 * mm,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["Normal"],
            fontName="KoreanSerif",
            fontSize=9.5,
            leading=14.5,
            textColor=DARK,
            wordWrap="CJK",
            borderColor=LINE,
            borderWidth=0.7,
            borderPadding=7,
            backColor=PALE_BLUE,
            spaceBefore=1 * mm,
            spaceAfter=2 * mm,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Normal"],
            fontName="Courier",
            fontSize=7.4,
            leading=9.8,
            textColor=DARK,
            backColor=LIGHT_GRAY,
            borderColor=colors.HexColor("#D9D9D9"),
            borderWidth=0.5,
            borderPadding=6,
            leftIndent=2 * mm,
            rightIndent=2 * mm,
            spaceAfter=2 * mm,
        ),
        "right_note": ParagraphStyle(
            "RightNote",
            parent=base["Normal"],
            fontName="KoreanSerif",
            fontSize=8.5,
            leading=12,
            textColor=MID_GRAY,
            alignment=TA_RIGHT,
        ),
    }


def P(text: str, styles: dict[str, ParagraphStyle], style: str = "body") -> Paragraph:
    return Paragraph(text, styles[style])


def bullet(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(f"• {text}", styles["bullet"])


def section_title(text: str, styles: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph(text, styles["h1"]),
        HRFlowable(width="100%", thickness=0.8, color=LINE, spaceAfter=2 * mm),
    ]


def cell(text: str, styles: dict[str, ParagraphStyle], style: str = "small") -> Paragraph:
    return Paragraph(text, styles[style])


def make_table(
    headers: list[str],
    rows: list[list[str]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
    center_columns: set[int] | None = None,
    font_size: float | None = None,
) -> Table:
    center_columns = center_columns or set()
    header_cells = [cell(value, styles, "small_bold") for value in headers]
    body_rows = []
    for row in rows:
        body_rows.append(
            [
                cell(value, styles, "small_center" if index in center_columns else "small")
                for index, value in enumerate(row)
            ]
        )
    table = Table([header_cells, *body_rows], colWidths=widths, repeatRows=1, hAlign="CENTER")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
        ("FONTNAME", (0, 0), (-1, 0), "KoreanSans"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#AAB7C4")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if font_size:
        commands.append(("FONTSIZE", (0, 0), (-1, -1), font_size))
    table.setStyle(TableStyle(commands))
    return table


def make_flow_diagram() -> Drawing:
    width = 168 * mm
    height = 49 * mm
    drawing = Drawing(width, height)

    boxes = [
        (4, 61, 84, 38, "사용자", "URL 입력 · 카테고리 선택"),
        (106, 61, 102, 38, "React + Vite", "화면 · 상태 · 접근성"),
        (230, 61, 102, 38, "FastAPI", "API · 검증 · 처리"),
        (354, 105, 112, 34, "웹 · RSS/Atom", "본문 · 기사 목록"),
        (354, 61, 112, 34, "Claude · DeepL", "요약 · 관찰 · 번역"),
        (354, 17, 112, 34, "SQLite · SMTP", "저장 · 발송 기록"),
    ]

    for x, y, w, h, title, description in boxes:
        drawing.add(Rect(x, y, w, h, 5, fillColor=PALE_BLUE, strokeColor=BLUE, strokeWidth=1))
        drawing.add(
            String(
                x + w / 2,
                y + h - 13,
                title,
                fontName="KoreanSans",
                fontSize=9,
                fillColor=NAVY,
                textAnchor="middle",
            )
        )
        drawing.add(
            String(
                x + w / 2,
                y + 9,
                description,
                fontName="KoreanSerif",
                fontSize=6.8,
                fillColor=DARK,
                textAnchor="middle",
            )
        )

    def arrow(x1: float, y1: float, x2: float, y2: float) -> None:
        drawing.add(Line(x1, y1, x2, y2, strokeColor=BLUE, strokeWidth=1.2))
        drawing.add(
            Polygon(
                [x2, y2, x2 - 6, y2 + 3, x2 - 6, y2 - 3],
                fillColor=BLUE,
                strokeColor=BLUE,
            )
        )

    arrow(88, 80, 106, 80)
    arrow(208, 80, 230, 80)
    arrow(332, 80, 354, 122)
    arrow(332, 80, 354, 78)
    arrow(332, 80, 354, 34)
    return drawing


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    page = canvas.getPageNumber()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#D9E2F3"))
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, height - 10.5 * mm, width - 20 * mm, height - 10.5 * mm)
    canvas.setFont("KoreanSans", 8)
    canvas.setFillColor(MID_GRAY)
    canvas.drawString(20 * mm, height - 8 * mm, "읽을게 | 프로젝트 보고서")
    canvas.setFont("KoreanSerif", 8)
    canvas.drawRightString(width - 20 * mm, 8 * mm, f"{page} / 6")
    canvas.restoreState()


def build_story(data: dict, styles: dict[str, ParagraphStyle]) -> list:
    highlights = data["presentation_highlights"]
    db_counts = data["local_database"]["table_counts"]
    story: list = []

    # Page 1
    story.extend(
        [
            Spacer(1, 8 * mm),
            P("PROJECT REPORT · 15점", styles, "kicker"),
            P("읽을게", styles, "title"),
            P("접근성 중심 RSS 뉴스 리더 및 뉴스레터 서비스", styles, "subtitle"),
            HRFlowable(width="100%", thickness=1.2, color=BLUE, spaceAfter=4 * mm),
        ]
    )
    meta_rows = [
        ["보고서 구분", "2차 프로젝트 최종 보고서"],
        ["학번 / 이름", "3208 / 윤유섭"],
        ["제출기한", "2026. 6. 21.(일)"],
        ["제출방법", "이메일 제출 (dsm2026@naver.com)"],
        ["소스코드", "rss-news 프로젝트 폴더 및 README.md"],
    ]
    story.append(make_table(["항목", "내용"], meta_rows, [34 * mm, 134 * mm], styles))
    story.append(Spacer(1, 4 * mm))
    story.extend(section_title("1. 개요 및 목표", styles))
    story.append(P("<b>가. 프로젝트 기획 의도</b>", styles, "h2"))
    story.append(
        P(
            "일반 웹페이지는 광고, 메뉴, 추천 영역, 팝업 등으로 본문에 집중하기 어렵고 사이트마다 "
            "글자 크기와 줄 간격이 달라 읽기 경험이 일관되지 않다. ‘읽을게’는 URL이나 RSS에서 "
            "기사의 제목·출처·본문을 추출해 동일한 리더뷰로 제공하고, 사용자가 자신의 읽기 환경을 "
            "직접 조절할 수 있도록 만든 웹 서비스이다.",
            styles,
        )
    )
    story.append(
        P(
            "최초 목표는 URL 본문 추출과 접근성 좋은 읽기 화면이었다. 개발 과정에서 RSS 기사 탐색, "
            "AI 요약·관찰 노트·번역, TTS, 사용자 카테고리, 주간 뉴스레터까지 확장하되 AI가 원문을 "
            "대체하지 않고 외부 서비스가 실패해도 핵심 읽기 기능은 유지하도록 설계하였다.",
            styles,
        )
    )
    story.append(P("<b>나. 최종 요구사항 및 기능 명세</b>", styles, "h2"))
    for item in [
        "URL 또는 RSS 기사에서 제목·출처·본문·단락을 추출하여 공통 리더뷰로 표시한다.",
        "글자 크기, 줄·문단 간격, 본문 폭, 밝음·어두움·고대비 테마를 지원한다.",
        "AI 요약·관찰 노트·질문 생성, DeepL 번역, Web Speech API 음성 읽기를 제공한다.",
        "사용자 RSS 카테고리와 이메일 구독, 주간 배치 발송 및 중복 방지 기록을 지원한다.",
        "잘못된 URL, 접근 차단, API 키 누락, SMTP 실패를 기능별 오류로 안내한다.",
    ]:
        story.append(bullet(item, styles))

    # Page 2
    story.append(PageBreak())
    story.extend(section_title("1. 개요 및 목표 (계속)", styles))
    story.append(P("다. 전체 시스템 구성", styles, "h2"))
    story.append(
        P(
            "프론트엔드는 React와 Vite가 화면·상태·접근성을 담당하고, FastAPI 서버가 URL 검증, "
            "본문 추출, RSS 파싱, 외부 API 호출, 뉴스레터 저장과 발송을 처리한다. 핵심 서비스 데이터는 "
            "SQLite에 저장하며 Supabase는 공개 테이블 조회를 통한 연결 검증 단계로 구분하였다.",
            styles,
        )
    )
    story.append(KeepTogether([make_flow_diagram(), P("그림 1. 읽을게 전체 시스템 흐름", styles, "caption")]))
    story.append(P("라. 최종 범위와 완료 판단", styles, "h2"))
    scope_rows = [
        ["핵심 범위", "URL 본문 추출, RSS 탐색, 리더뷰, 읽기 설정", "완료"],
        ["AI 보조", "요약, 관찰 노트, 질문 생성, 번역, TTS", "완료"],
        ["뉴스레터", "구독, 미리보기, SMTP, 주간 배치, 해지", "완료"],
        ["데이터", "SQLite 저장, Supabase 연결 검증", "부분 완료"],
        ["제외 범위", "사용자 계정, 북마크, 읽기 기록, 실제 배포", "후속"],
    ]
    story.append(make_table(["구분", "구현 범위", "상태"], scope_rows, [28 * mm, 112 * mm, 28 * mm], styles, {2}))
    story.append(Spacer(1, 3 * mm))
    story.extend(section_title("2. 기능 구현 및 결과", styles))
    story.append(
        P(
            "주요 기능은 본문 추출, RSS 큐레이션, AI 보조 기능, 뉴스레터, 접근성 UI의 다섯 영역으로 "
            "구현하였다. 아래 기능별 설명에는 구현 내용, 결과와 예외 상황 처리를 함께 정리하였다.",
            styles,
        )
    )
    feature_summary = [
        ["1", "URL 본문 추출", "직접 추출 → 단락 보완 → RSS fallback"],
        ["2", "RSS·아이디어 레이더", "8개 기본 카테고리와 사용자 카테고리"],
        ["3", "AI·번역·TTS", "사용자 요청 시 선택적으로 실행"],
        ["4", "뉴스레터", "구독·배치·중복 방지·상태 기록"],
        ["5", "접근성 UI", "읽기 설정·상태 안내·반응형 화면"],
    ]
    story.append(make_table(["번호", "기능", "핵심 결과"], feature_summary, [14 * mm, 48 * mm, 106 * mm], styles, {0}))

    # Page 3
    story.append(PageBreak())
    story.extend(section_title("2. 기능 구현 및 결과", styles))
    story.append(P("가. 기능 1 - URL 본문 추출과 공통 리더뷰", styles, "h2"))
    story.append(
        P(
            "<b>구현 내용:</b> 사용자가 URL을 입력하면 httpx로 HTML을 가져오고 trafilatura를 우선 사용해 "
            "본문을 추출한다. 결과가 짧으면 BeautifulSoup으로 단락을 보완하며 직접 접근이 차단되면 공식 "
            "RSS/Atom 항목의 URL·GUID·ID를 비교해 본문을 복구한다. 프로토콜이 없는 주소는 HTTPS로 보정한다.",
            styles,
            "body_tight",
        )
    )
    story.append(
        P(
            "<b>예외 상황 처리:</b> FTP 등 지원하지 않는 프로토콜, 비HTML 응답, 봇 차단, RSS 미발견을 "
            "구분해 사용자에게 원인별 메시지를 보여준다. 외부 페이지가 실패해도 데모 기사와 RSS 읽기는 유지된다.",
            styles,
            "body_tight",
        )
    )
    story.append(P("나. 기능 2 - RSS 카테고리와 아이디어 레이더", styles, "h2"))
    story.append(
        P(
            f"<b>구현 내용:</b> 기본 RSS 카테고리 {highlights['default_rss_category_count']}개와 고유 피드 "
            f"{highlights['unique_default_feed_count']}개를 사용해 기사 목록을 구성하고 URL 중복 제거, "
            "키워드 필터, 최신순 정렬을 적용하였다. 사용자는 카테고리 이름과 검색 힌트로 RSS 후보를 찾아 "
            "저장할 수 있으며 현재 저장 카테고리는 11개, 사용자 정의 카테고리는 3개이다.",
            styles,
            "body_tight",
        )
    )
    image = Image(str(NEWS_IMAGE), width=168 * mm, height=105 * mm)
    story.append(KeepTogether([image, P("그림 2. 아이디어 레이더와 RSS 기사 목록 실행 화면", styles, "caption")]))
    story.append(
        P(
            "<b>실행 결과:</b> 2026년 6월 24일 로컬 시연에서 아이디어 레이더 API가 기사 12건을 반환했고, "
            "대표 기사와 후속 기사가 목차형 화면에 표시되었다.",
            styles,
            "callout",
        )
    )

    # Page 4
    story.append(PageBreak())
    story.extend(section_title("2. 기능 구현 및 결과 (계속)", styles))
    story.append(P("다. 기능 3 - AI 요약·관찰 노트·번역·TTS", styles, "h2"))
    story.append(
        P(
            "<b>구현 내용:</b> Claude API는 핵심 요약, 질문 프롬프트, 읽을 이유·변화 신호·불편과 욕망·"
            "아이디어 힌트를 포함한 관찰 노트를 구조화된 JSON으로 반환한다. DeepL은 영어·일본어·중국어 "
            "번역을 담당하고 Web Speech API는 단락별 읽기, 일시정지, 재개와 정지를 처리한다.",
            styles,
            "body_tight",
        )
    )
    story.append(
        P(
            "<b>예외 상황 처리:</b> API 키가 없거나 호출이 실패하면 해당 기능만 비활성화하고 원문 읽기는 "
            "계속 사용할 수 있다. AI가 낮은 신호를 반환하면 억지로 내용을 생성하지 않고 주의 문구를 표시한다.",
            styles,
            "body_tight",
        )
    )
    story.append(P("라. 기능 4 - 뉴스레터 구독과 정기 발송", styles, "h2"))
    story.append(
        P(
            "<b>구현 내용:</b> 이메일·카테고리·주간 주기를 SQLite에 저장하고 최근 RSS 기사로 텍스트·HTML "
            "digest를 생성한다. ISO 주차별 발송 시도에 고유 제약을 적용해 같은 주의 중복 발송을 방지하고 "
            "claimed·sent·failed 상태와 성공·실패 시각을 기록한다. CLI, dry-run, 관리자 API와 해지 API도 제공한다.",
            styles,
            "body_tight",
        )
    )
    story.append(P("마. 기능 5 - 사용자 화면과 접근성", styles, "h2"))
    story.append(
        P(
            "뉴스 읽기, URL 입력, 리더뷰 화면을 분리하고 글자 크기 18px, 줄 간격 1.75, 문단 간격 1.4, "
            "본문 폭 720px을 기본 설정으로 제공한다. label, aria-live, role=alert, dialog, aria-modal을 "
            "적용했으며 760px 이하에서는 화면을 한 열로 재배치한다.",
            styles,
            "body_tight",
        )
    )
    image = Image(str(URL_IMAGE), width=168 * mm, height=81.7 * mm)
    story.append(KeepTogether([image, P("그림 3. URL 입력 및 샘플 문서 선택 화면", styles, "caption")]))
    result_rows = [
        ["API", f"{highlights['api_endpoint_count']}개 엔드포인트", "구현"],
        ["데모 본문", "121어절 · 4개 단락 추출", "성공"],
        ["백엔드", "단위 테스트 13건", "전체 통과"],
        ["프론트엔드", "Vite production build", "통과"],
    ]
    story.append(make_table(["검증 항목", "측정 결과", "판정"], result_rows, [38 * mm, 94 * mm, 36 * mm], styles, {2}))

    # Page 5
    story.append(PageBreak())
    story.extend(section_title("3. 서비스 연동 및 데이터 처리", styles))
    story.append(P("가. 외부 서비스 연동 내역", styles, "h2"))
    service_rows = [
        ["RSS/Atom", "기사 목록·링크·발행일·요약", "실패 소스를 건너뛰고 계속 수집"],
        ["Claude API", "요약·관찰 노트·검색 힌트", "키가 없으면 AI 기능만 비활성"],
        ["DeepL API", "영·일·중 본문 번역", "키·사용량 오류를 안내문으로 변환"],
        ["SMTP", "텍스트·HTML 뉴스레터", "설정 없으면 구독만 저장"],
        ["Supabase", "public.todos 조회 검증", "현재 조회 불가, 핵심 DB 이전 미완료"],
    ]
    story.append(make_table(["서비스", "연동 목적", "실패·제약 처리"], service_rows, [28 * mm, 62 * mm, 78 * mm], styles))
    story.append(P("나. 데이터 처리 방법", styles, "h2"))
    story.append(
        P(
            f"SQLite는 카테고리 {db_counts['newsletter_categories']}건, 카테고리 출처 "
            f"{db_counts['newsletter_category_sources']}건, 구독 {db_counts['newsletter_subscriptions']}건, "
            f"발송 시도 {db_counts['newsletter_delivery_attempts']}건을 저장한다. 보고서용 데이터 추출에서는 "
            "이메일, 해지 토큰, 내부 식별자와 환경변수 값을 제외하고 집계 데이터만 사용하였다.",
            styles,
        )
    )
    processing_rows = [
        ["기사 탐색", "RSS 수집 → URL 중복 제거 → 키워드 필터 → 최신순 정렬"],
        ["본문 읽기", "URL 검증 → HTML 추출 → 단락 보완 → 실패 시 RSS fallback"],
        ["AI 보조", "제목·본문 전달 → 구조화 응답 검증 → 리더뷰 패널 표시"],
        ["뉴스레터", "구독 조회 → 주차 선점 → digest 생성 → SMTP → 상태 기록"],
    ]
    story.append(make_table(["처리 구간", "데이터 흐름"], processing_rows, [36 * mm, 132 * mm], styles))
    story.extend(section_title("4. 유지보수 계획", styles))
    story.append(P("가. 주요 핵심 코드 설명", styles, "h2"))
    story.append(
        P(
            "아래 조건은 활성 주간 구독 중 현재 ISO 주차에 발송 시도가 없는 대상만 선택한다. "
            "조회와 별도로 발송 시도 테이블의 고유 제약을 사용하므로 배치가 동시에 실행되어도 중복 처리 가능성을 낮춘다.",
            styles,
            "body_tight",
        )
    )
    code = (
        "WHERE status = 'active'\n"
        "  AND cadence = 'weekly'\n"
        "  AND NOT EXISTS (\n"
        "    SELECT 1 FROM newsletter_delivery_attempts AS attempt\n"
        "    WHERE attempt.subscription_id = subscription.id\n"
        "      AND attempt.delivery_window = ?\n"
        "  )"
    )
    story.append(P(code.replace("\n", "<br/>").replace(" ", "&nbsp;"), styles, "code"))
    story.append(P("나. 유지보수 계획", styles, "h2"))
    maintenance_rows = [
        ["우선", "Supabase 선택 초기화 및 핵심 데이터 마이그레이션"],
        ["우선", "이메일+카테고리 중복 구독 방지와 해지 링크 연결"],
        ["단기", "키보드·포커스·색 대비·스크린리더 접근성 검증"],
        ["단기", "프론트·백엔드 배포와 외부 스케줄러 연결"],
        ["중기", "사용자 인증, 북마크, 읽기 기록, 설정 동기화"],
    ]
    story.append(make_table(["우선순위", "계획"], maintenance_rows, [30 * mm, 138 * mm], styles, {0}))

    # Page 6
    story.append(PageBreak())
    story.extend(section_title("5. 결론 및 고찰", styles))
    story.append(P("가. 최종 시연 결과", styles, "h2"))
    demo_rows = [
        ["서버 상태", "GET /api/health", "정상"],
        ["URL 본문 추출", "데모 기사 121어절·4단락 반환", "성공"],
        ["RSS 기사 탐색", "아이디어 레이더 기사 12건 반환", "성공"],
        ["데이터", "저장 카테고리 11개·활성 구독 2건", "확인"],
        ["품질 검증", "백엔드 테스트 13건·프론트 빌드", "통과"],
    ]
    story.append(make_table(["시연 항목", "결과", "판정"], demo_rows, [38 * mm, 94 * mm, 36 * mm], styles, {2}))
    story.append(
        P(
            "발표 자료와 소스코드에서 뉴스 탐색, URL 입력, 리더뷰, AI 보조 기능, 뉴스레터 처리 흐름을 "
            "순서대로 설명할 수 있으며 로컬 환경에서 핵심 시나리오를 재현하였다. Claude·DeepL·SMTP의 실제 호출은 "
            "각 서비스 키와 계정 설정이 필요하므로 자동 검증 범위와 분리하였다.",
            styles,
        )
    )
    story.append(P("나. 프로젝트 목표 달성도", styles, "h2"))
    story.append(
        P(
            "최초 목표인 ‘복잡한 웹 콘텐츠를 읽기 쉽고 접근성 좋은 형태로 제공한다’는 달성하였다. "
            "URL과 RSS라는 서로 다른 입력을 공통 리더뷰로 연결했고 사용자가 읽기 설정을 조절할 수 있게 했다. "
            "추가로 AI 기능과 뉴스레터까지 구현해 단순 본문 추출 도구에서 읽기 중심 콘텐츠 서비스로 확장하였다.",
            styles,
        )
    )
    story.append(P("다. 고찰 및 배운 점", styles, "h2"))
    for item in [
        "웹 본문 추출은 단일 라이브러리보다 HTML·메타데이터·RSS fallback을 조합해야 안정적이었다.",
        "AI 기능은 결과의 양보다 원문과 해석을 분리하고 실패 시 핵심 기능을 유지하는 설계가 중요했다.",
        "이메일 발송은 전송 기능보다 중복 방지, 실패 기록, dry-run과 재실행 가능성을 먼저 설계해야 했다.",
        "접근성은 ARIA 속성만으로 완료되지 않으며 실제 키보드와 보조기기 검증이 필요하다.",
    ]:
        story.append(bullet(item, styles))
    story.append(P("라. 추후 심화 연구 방향", styles, "h2"))
    story.append(
        P(
            "향후에는 Supabase Auth와 RLS를 적용해 사용자별 카테고리·북마크·읽기 기록을 안전하게 분리하고, "
            "SQLite 데이터를 외부 DB로 이전할 계획이다. 동시에 뉴스레터 실패 재시도와 운영 로그, 실제 배포 환경의 "
            "스케줄러, 자동 접근성 검사와 스크린리더 테스트를 추가해 기능형 MVP를 운영 가능한 서비스로 발전시키고자 한다.",
            styles,
        )
    )
    story.append(
        P(
            "<b>최종 평가:</b> 핵심 읽기 경험과 평가 대상 기능은 구현되었다. 다만 Supabase 전체 이전, 사용자 인증, "
            "실제 배포와 종합 접근성 검증은 남아 있으므로 현재 결과물은 기능이 검증된 MVP로 판단한다.",
            styles,
            "callout",
        )
    )
    story.append(P("참고 및 제출 자료", styles, "h2"))
    story.append(
        P(
            "README.md · docs/reports/second-report.md · third-report.md · fourth-report.md · "
            "server/test_parse_request.py · test_article_insight.py · test_newsletter_delivery.py · "
            "test_export_presentation_data.py",
            styles,
            "small",
        )
    )
    story.append(P("작성 기준일: 2026. 6. 24.", styles, "right_note"))
    return story


def main() -> None:
    register_fonts()
    styles = build_styles()
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=14 * mm,
        title="읽을게 프로젝트 보고서",
        author="윤유섭",
        subject="접근성 중심 RSS 뉴스 리더 및 뉴스레터 서비스",
        keywords="React, FastAPI, RSS, 접근성, 뉴스레터",
    )
    document.build(build_story(data, styles), onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUTPUT)


if __name__ == "__main__":
    main()
