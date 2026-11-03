"""
네이버 뉴스 크롤러 GUI (PyQt6)

필요 패키지:
    pip install requests beautifulsoup4 PyQt6
"""

import csv
import html
import os
import sys
import time

import requests
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from naver_news_crawler import build_search_url, collect_article_links, parse_article

COLUMNS = [("title", "제목"), ("press", "언론사"), ("date", "작성일")]

# 엑셀 저장 시 열 구성: (키, 머리글, 열 너비)
EXCEL_COLUMNS = [
    ("title", "제목", 50),
    ("press", "언론사", 14),
    ("date", "작성일", 20),
    ("url", "URL", 45),
    ("content", "본문", 100),
]
EXCEL_CELL_LIMIT = 32767  # 엑셀 셀 하나에 들어갈 수 있는 최대 글자 수

# 언론사 이름에 따라 돌아가며 쓰는 배지 색상
BADGE_COLORS = ["#7B61FF", "#00A3FF", "#FF6B6B", "#FF9F1C", "#03C75A", "#E056FD", "#2EC4B6"]

STYLE_SHEET = """
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EEF2FF, stop:1 #F0FFF6);
}
QWidget { font-family: "Malgun Gothic"; font-size: 10pt; color: #1F2937; }

#banner {
    border-radius: 18px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #03C75A, stop:0.5 #00A3FF, stop:1 #7B61FF);
}
#bannerTitle { color: white; font-size: 22pt; font-weight: 800; background: transparent; }
#bannerSub { color: rgba(255,255,255,0.85); font-size: 10pt; background: transparent; }

#card { background: white; border-radius: 16px; }
#sectionTitle { font-size: 12pt; font-weight: 700; color: #111827; }
#countBadge {
    color: white; font-weight: 700; padding: 3px 12px; border-radius: 11px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF6B6B, stop:1 #FF9F1C);
}

QLineEdit {
    border: 2px solid #E5E7EB; border-radius: 12px; padding: 9px 14px;
    font-size: 11pt; background: #F9FAFB;
}
QLineEdit:focus { border: 2px solid #00A3FF; background: white; }

QPushButton {
    color: white; font-weight: 700; border: none; border-radius: 12px;
    padding: 10px 20px; min-width: 70px;
}
#startBtn { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #03C75A, stop:1 #00A3FF); }
#startBtn:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #02B350, stop:1 #008FE0); }
#stopBtn { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF6B6B, stop:1 #FF3D71); }
#stopBtn:hover { background: #E8455F; }
#csvBtn { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7B61FF, stop:1 #A06BFF); }
#csvBtn:hover { background: #6A4FF0; }
#excelBtn { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D6F42, stop:1 #21A366); }
#excelBtn:hover { background: #185C37; }
QPushButton:pressed { padding-top: 12px; padding-bottom: 8px; }
/* 버튼별 색상(#id)보다 우선하도록 비활성 스타일도 id로 지정 */
#startBtn:disabled, #stopBtn:disabled, #csvBtn:disabled, #excelBtn:disabled {
    background: #E5E7EB; color: #9CA3AF;
}

QTableWidget {
    border: none; background: white; alternate-background-color: #F6F8FF;
    selection-background-color: transparent; gridline-color: transparent;
}
QTableWidget::item { padding: 6px 10px; border-bottom: 1px solid #F1F3F9; }
QTableWidget::item:selected {
    color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00A3FF, stop:1 #7B61FF);
}
QHeaderView::section {
    background: #F3F4FF; color: #4B5563; font-weight: 700; border: none;
    padding: 9px; border-bottom: 2px solid #E0E4FF;
}

QTextBrowser { border: none; background: white; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 4px; }
QScrollBar::handle:vertical { background: #C7D2FE; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #818CF8; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }

QSplitter::handle { background: transparent; height: 12px; }

QProgressBar {
    border: none; border-radius: 7px; background: #E5E7EB;
    height: 14px; min-width: 220px; text-align: center; font-size: 8pt; color: #374151;
}
QProgressBar::chunk {
    border-radius: 7px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #03C75A, stop:1 #00A3FF);
}
QStatusBar { background: transparent; color: #4B5563; }
QStatusBar::item { border: none; }
"""


def resource_path(name):
    """PyInstaller로 묶인 실행 파일에서는 임시 폴더(_MEIPASS)에서 리소스를 찾음"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def badge_color(press):
    """같은 언론사는 항상 같은 색이 나오도록 이름으로 색 선택"""
    return BADGE_COLORS[sum(map(ord, press)) % len(BADGE_COLORS)]


def add_shadow(widget, blur=30, alpha=40):
    """카드가 떠 있는 것처럼 보이도록 그림자 효과 추가"""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(80, 70, 200, alpha))
    widget.setGraphicsEffect(shadow)


def make_card(title, widget, extra=None):
    """제목과 내용 위젯을 흰색 둥근 카드로 감쌈"""
    card = QFrame()
    card.setObjectName("card")
    add_shadow(card)

    header = QHBoxLayout()
    label = QLabel(title)
    label.setObjectName("sectionTitle")
    header.addWidget(label)
    header.addStretch()
    if extra:
        header.addWidget(extra)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 14, 18, 18)
    layout.setSpacing(10)
    layout.addLayout(header)
    layout.addWidget(widget)
    return card


class CrawlWorker(QThread):
    """크롤링은 시간이 걸리므로 별도 스레드에서 실행해 화면이 멈추지 않게 함"""

    links_found = pyqtSignal(int)
    article_done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            links = collect_article_links(self.url)
        except requests.RequestException as e:
            self.failed.emit(f"검색 페이지를 불러오지 못했습니다.\n{e}")
            return

        self.links_found.emit(len(links))
        for url in links:
            if self._stop:
                break
            try:
                self.article_done.emit(parse_article(url))
            except requests.RequestException:
                self.article_done.emit({})  # 실패한 기사도 진행률은 올림
            time.sleep(0.5)  # 서버 부하를 줄이기 위한 요청 간격


def write_excel(path, articles, keyword=""):
    """수집한 기사를 서식이 적용된 엑셀(.xlsx) 파일로 저장"""
    wb = Workbook()
    ws = wb.active
    ws.title = "뉴스"

    ws.append([label for _, label, _ in EXCEL_COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="03C75A")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for art in articles:
        # 엑셀에 넣을 수 없는 제어 문자를 지우고, 셀 글자 수 제한에 맞춰 자름
        ws.append([ILLEGAL_CHARACTERS_RE.sub("", art[key])[:EXCEL_CELL_LIMIT] for key, _, _ in EXCEL_COLUMNS])
        url_cell = ws.cell(row=ws.max_row, column=4)
        url_cell.hyperlink = url_cell.value
        url_cell.font = Font(color="0563C1", underline="single")

    for i, (_, _, width) in enumerate(EXCEL_COLUMNS, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column == 5)
        ws.row_dimensions[row[0].row].height = 90  # 본문 앞부분이 보이도록 행 높이 지정

    ws.freeze_panes = "A2"  # 머리글 행 고정
    ws.auto_filter.ref = ws.dimensions
    if keyword:
        wb.properties.title = f"네이버 뉴스 - {keyword}"
    wb.save(path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📰 네이버 뉴스 크롤러")
        self.resize(1180, 820)
        self.setStyleSheet(STYLE_SHEET)
        self.articles = []
        self.worker = None

        # 상단 그라데이션 배너
        banner = QFrame()
        banner.setObjectName("banner")
        add_shadow(banner, blur=40, alpha=70)
        banner_title = QLabel("📰  네이버 뉴스 크롤러")
        banner_title.setObjectName("bannerTitle")
        banner_sub = QLabel("검색어를 입력하면 네이버 뉴스 기사를 모아 본문까지 한눈에 보여드려요 ✨")
        banner_sub.setObjectName("bannerSub")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(26, 18, 26, 18)
        banner_layout.setSpacing(4)
        banner_layout.addWidget(banner_title)
        banner_layout.addWidget(banner_sub)

        # 검색 영역
        self.keyword_edit = QLineEdit("반도체")
        self.keyword_edit.setPlaceholderText("🔍  검색어 또는 네이버 검색 URL 입력")
        self.keyword_edit.returnPressed.connect(self.start_crawl)
        self.search_btn = self.make_button("🚀 크롤링 시작", "startBtn", self.start_crawl)
        self.stop_btn = self.make_button("⏹ 중지", "stopBtn", self.stop_crawl)
        self.save_btn = self.make_button("📄 CSV 저장", "csvBtn", self.save_csv)
        self.excel_btn = self.make_button("📊 엑셀 저장", "excelBtn", self.save_excel)

        search_card = QFrame()
        search_card.setObjectName("card")
        add_shadow(search_card)
        top = QHBoxLayout(search_card)
        top.setContentsMargins(16, 14, 16, 14)
        top.setSpacing(10)
        top.addWidget(self.keyword_edit, 1)
        top.addWidget(self.search_btn)
        top.addWidget(self.stop_btn)
        top.addWidget(self.save_btn)
        top.addWidget(self.excel_btn)

        # 기사 목록
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _, label in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setHighlightSections(False)
        self.table.itemSelectionChanged.connect(self.show_article)

        self.count_badge = QLabel("0건")
        self.count_badge.setObjectName("countBadge")

        # 기사 본문
        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)
        self.show_placeholder()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(make_card("🗂  기사 목록", self.table, self.count_badge))
        splitter.addWidget(make_card("📖  기사 본문", self.viewer))
        splitter.setSizes([330, 450])

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.status_label = QLabel("💡 검색어를 입력하고 [크롤링 시작]을 누르세요.")
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.progress)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 6)
        layout.setSpacing(14)
        layout.addWidget(banner)
        layout.addWidget(search_card)
        layout.addWidget(splitter, 1)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.set_running(False)

    def make_button(self, text, name, slot):
        btn = QPushButton(text)
        btn.setObjectName(name)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    def show_placeholder(self):
        self.viewer.setHtml(
            "<div style='text-align:center; color:#9CA3AF; margin-top:60px'>"
            "<p style='font-size:36pt'>🗞️</p>"
            "<p style='font-size:12pt'>목록에서 기사를 선택하면 본문이 여기에 표시됩니다.</p></div>"
        )

    def start_crawl(self):
        text = self.keyword_edit.text().strip()
        if not text or (self.worker and self.worker.isRunning()):
            return
        url = text if text.startswith("http") else build_search_url(text)

        self.articles.clear()
        self.table.setRowCount(0)
        self.count_badge.setText("0건")
        self.show_placeholder()
        self.set_running(True)
        self.status_label.setText("🔎 검색 결과에서 기사 링크를 찾는 중...")

        self.worker = CrawlWorker(url)
        self.worker.links_found.connect(self.on_links_found)
        self.worker.article_done.connect(self.on_article_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def stop_crawl(self):
        if self.worker:
            self.worker.stop()
            self.status_label.setText("⏳ 중지하는 중...")

    def set_running(self, running):
        self.search_btn.setEnabled(not running)
        self.keyword_edit.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.save_btn.setEnabled(not running and bool(self.articles))
        self.excel_btn.setEnabled(not running and bool(self.articles))
        self.progress.setVisible(running)

    def on_links_found(self, count):
        self.progress.setRange(0, max(count, 1))
        self.progress.setValue(0)
        self.status_label.setText(f"📡 기사 {count}개 발견, 본문 수집 중...")

    def on_article_done(self, article):
        self.progress.setValue(self.progress.value() + 1)
        if not article:
            return
        self.articles.append(article)
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, (key, _) in enumerate(COLUMNS):
            item = QTableWidgetItem(article[key])
            if key == "press":
                # 언론사 이름은 언론사마다 고정된 색의 굵은 글씨로 표시
                item.setForeground(QColor(badge_color(article["press"])))
                font = QFont()
                font.setBold(True)
                item.setFont(font)
            elif key == "date":
                item.setForeground(QColor("#6B7280"))
            self.table.setItem(row, col, item)
        self.count_badge.setText(f"{len(self.articles)}건")
        if row == 0:
            self.table.selectRow(0)

    def on_failed(self, message):
        QMessageBox.warning(self, "오류", message)

    def on_finished(self):
        self.set_running(False)
        self.status_label.setText(f"✅ 완료: 기사 {len(self.articles)}건 수집")

    def show_article(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        raw = self.articles[rows[0].row()]
        art = {k: html.escape(v) for k, v in raw.items()}
        # 기사 내용이 HTML 태그로 해석되지 않도록 escape 후 줄바꿈만 <br>로 변환
        content = art["content"].replace("\n", "<br>")
        color = badge_color(raw["press"])
        self.viewer.setHtml(
            f"<table cellspacing='0' cellpadding='0'><tr>"
            f"<td style='background:{color}; color:white; font-weight:bold; padding:4px 12px;'>"
            f"&nbsp;{art['press']}&nbsp;</td>"
            f"<td style='color:#6B7280; padding-left:10px;'>&nbsp;🕒 {art['date']}</td>"
            f"</tr></table>"
            f"<h1 style='color:#111827; font-size:19pt; margin-top:12px'>{art['title']}</h1>"
            f"<p><a style='color:#00A3FF; text-decoration:none' href='{art['url']}'>🔗 원문 보기 · {art['url']}</a></p>"
            f"<hr style='background:#E5E7EB; height:1px; border:none'>"
            f"<p style='font-size:11.5pt; line-height:170%; color:#374151'>{content}</p>"
        )

    def save_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", "naver_news.csv", "CSV 파일 (*.csv)")
        if not path:
            return
        # 엑셀에서 한글이 깨지지 않도록 utf-8-sig로 저장
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "press", "date", "url", "content"])
            writer.writeheader()
            writer.writerows(self.articles)
        self.status_label.setText(f"{path} 에 {len(self.articles)}건 저장 완료")

    def save_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "엑셀 저장", "naver_news.xlsx", "엑셀 파일 (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            write_excel(path, self.articles, self.keyword_edit.text().strip())
        except PermissionError:
            QMessageBox.warning(self, "오류", "파일이 다른 프로그램(엑셀 등)에서 열려 있어 저장할 수 없습니다.")
            return
        self.status_label.setText(f"{path} 에 {len(self.articles)}건 저장 완료")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        event.accept()


if __name__ == "__main__":
    if sys.platform == "win32":
        # 작업 표시줄에 python 아이콘 대신 앱 아이콘이 표시되도록 앱 ID 지정
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("naver.news.crawler")
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("app.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
