"""
코스피200 크롤러 GUI (PyQt6)

kospi200_crawler.py 의 크롤링 함수를 백그라운드 스레드에서 실행하고,
지수 요약과 구성종목 201개를 화면에 보여 줍니다.

필요 패키지:
    pip install requests beautifulsoup4 PyQt6 openpyxl
"""

import sys
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kospi200_crawler import (
    OUTPUT_CSV,
    STOCKS_CSV,
    crawl,
    crawl_stocks,
    save_csv,
    save_stocks_csv,
)

STOCK_COLUMNS = [
    "순위", "종목코드", "종목명", "현재가", "전일대비", "등락률(%)",
    "거래량", "거래대금(백만)", "시가총액(억)",
]
NUMERIC_COLUMNS = {"순위", "현재가", "전일대비", "등락률(%)", "거래량", "거래대금(백만)", "시가총액(억)"}
SIGNED_COLUMNS = {"전일대비", "등락률(%)"}

# 국내 증시 관례: 상승은 빨강, 하락은 파랑
RISE_COLOR = "#E5383B"
FALL_COLOR = "#2563EB"
FLAT_COLOR = "#6B7280"

# 요약 카드의 숫자 타일: (데이터 키, 화면 표시 이름) — 2줄 × 6칸
SUMMARY_TILES = [
    ("전일", "전일"), ("시가", "시가"), ("고가", "고가"),
    ("저가", "저가"), ("거래량", "거래량"), ("거래대금", "거래대금"),
    ("투자자별_개인", "개인"), ("투자자별_외국인", "외국인"), ("투자자별_기관", "기관"),
    ("등락종목_상승", "상승 종목"), ("등락종목_보합", "보합 종목"), ("등락종목_하락", "하락 종목"),
]
SIGNED_TILES = {"투자자별_개인", "투자자별_외국인", "투자자별_기관"}

# 색은 상승/하락 표시에만 쓰고, 나머지는 흰색·회색 계열로 단순하게 둡니다.
STYLE_SHEET = """
QMainWindow, #root { background: #F5F6F8; }
QWidget { font-family: "Malgun Gothic"; font-size: 10pt; color: #111827; }

#appTitle { font-size: 18pt; font-weight: 800; }
#status { color: #6B7280; }

#card { background: white; border: 1px solid #E5E7EB; border-radius: 12px; }
#tile { background: #F9FAFB; border-radius: 8px; }
#tileKey { color: #6B7280; font-size: 9pt; background: transparent; }
#tileValue { font-size: 13pt; font-weight: 700; background: transparent; }

#indexName { color: #6B7280; font-size: 11pt; font-weight: 700; }
#indexPrice { font-size: 34pt; font-weight: 800; }
#changePill { font-size: 11pt; font-weight: 700; padding: 4px 10px; border-radius: 6px; }
#subInfo { color: #9CA3AF; font-size: 9pt; }

#sectionTitle { font-size: 12pt; font-weight: 700; }
#count { color: #6B7280; font-weight: 700; }

QLineEdit {
    border: 1px solid #E5E7EB; border-radius: 8px; padding: 7px 12px; background: white;
}
QLineEdit:focus { border-color: #111827; }

QPushButton {
    border-radius: 8px; padding: 8px 16px; font-weight: 700;
    border: 1px solid #D1D5DB; background: white; color: #111827;
}
QPushButton:hover { background: #F3F4F6; }
QPushButton:disabled { color: #C4C8CF; border-color: #E5E7EB; background: white; }
#primaryButton { background: #111827; border-color: #111827; color: white; }
#primaryButton:hover { background: #374151; }
#primaryButton:disabled { background: #9CA3AF; border-color: #9CA3AF; color: white; }

QTableWidget {
    border: none; background: white; outline: 0;
    selection-background-color: #F3F4F6; selection-color: #111827;
}
QTableWidget::item { border-bottom: 1px solid #F3F4F6; padding: 0 8px; }
QHeaderView::section {
    background: white; border: none; border-bottom: 1px solid #E5E7EB;
    padding: 8px; font-weight: 700; color: #6B7280;
}

QProgressBar { border: none; background: #E5E7EB; border-radius: 2px; }
QProgressBar::chunk { background: #111827; border-radius: 2px; }
"""

PILL_BACKGROUND = {RISE_COLOR: "#FDECEC", FALL_COLOR: "#EAF1FE", FLAT_COLOR: "#F3F4F6"}


def to_number(text):
    """'1,234', '+15,389', '-4.02', '53 (1)' 같은 문자열에서 정렬용 숫자를 뽑습니다."""
    text = text.split("(")[0].replace(",", "").replace("+", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def sign_color(text):
    value = to_number(text)
    if value > 0:
        return RISE_COLOR
    if value < 0:
        return FALL_COLOR
    return FLAT_COLOR


def is_plain_number(text):
    """'1,234' / '+15,389' / '-4.02' 처럼 숫자로만 된 값인지 ('9조 6,043억', '53 (1)' 은 제외)."""
    stripped = text.replace(",", "").replace("+", "").replace("-", "").replace(".", "")
    return stripped.isdigit()


# 엑셀 구성종목 시트: (열 이름, 너비, 숫자 서식)
EXCEL_STOCK_COLUMNS = [
    ("순위", 7, "0"),
    ("종목코드", 11, None),
    ("종목명", 20, None),
    ("현재가", 13, "#,##0"),
    ("전일대비", 12, "+#,##0;-#,##0;0"),
    ("등락률(%)", 11, "+0.00;-0.00;0.00"),
    ("거래량", 15, "#,##0"),
    ("거래대금(백만)", 16, "#,##0"),
    ("시가총액(억)", 15, "#,##0"),
    ("기준시각", 27, None),
]
EXCEL_HEADER_FILL = PatternFill("solid", fgColor="111827")
EXCEL_THIN = Side(style="thin", color="E5E7EB")


def style_header(row):
    for cell in row:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = EXCEL_HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")


def write_excel(path, summary, stocks):
    """구성종목과 지수 요약을 시트 두 개짜리 엑셀(.xlsx) 파일로 저장합니다."""
    wb = Workbook()

    # 1) 구성종목 시트: 숫자는 숫자 형식으로 넣어 엑셀에서 바로 정렬·계산할 수 있게 합니다.
    ws = wb.active
    ws.title = "구성종목"
    ws.append([name for name, _, _ in EXCEL_STOCK_COLUMNS])
    style_header(ws[1])

    for stock in stocks:
        ws.append([
            to_number(str(stock[name])) if fmt else stock[name]
            for name, _, fmt in EXCEL_STOCK_COLUMNS
        ])
        color = sign_color(stock["전일대비"]).lstrip("#")
        for col, (name, _, fmt) in enumerate(EXCEL_STOCK_COLUMNS, 1):
            cell = ws.cell(row=ws.max_row, column=col)
            cell.border = Border(bottom=EXCEL_THIN)
            if fmt:
                cell.number_format = fmt
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="center")
            if name in SIGNED_COLUMNS or name == "현재가":
                cell.font = Font(color=color)

    for col, (_, width, _) in enumerate(EXCEL_STOCK_COLUMNS, 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
    ws.freeze_panes = "A2"  # 머리글 행 고정
    ws.auto_filter.ref = ws.dimensions

    # 2) 지수 요약 시트: 항목 / 값 두 열
    ws = wb.create_sheet("지수요약")
    ws.append(["항목", "값"])
    style_header(ws[1])
    for key, value in summary.items():
        if is_plain_number(value):
            ws.append([key, to_number(value)])
            cell = ws.cell(row=ws.max_row, column=2)
            cell.number_format = "#,##0.00" if "." in value else "#,##0"
            if key in ("전일대비", "등락률(%)") or key.startswith(("투자자별", "프로그램")):
                cell.font = Font(bold=True, color=sign_color(value).lstrip("#"))
        else:
            ws.append([key, value])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, color="374151")
        ws.cell(row=ws.max_row, column=2).alignment = Alignment(horizontal="right")
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 22

    wb.properties.title = f"코스피200 - {summary.get('기준일', '')}"
    wb.save(path)


class NumericItem(QTableWidgetItem):
    """콤마가 들어간 숫자도 크기순으로 정렬되도록 하는 셀."""

    def __lt__(self, other):
        return to_number(self.text()) < to_number(other.text())


class CrawlWorker(QThread):
    """지수 요약 → 구성종목 순서로 수집합니다. 네트워크 작업이라 UI 스레드와 분리합니다."""

    summary_done = pyqtSignal(dict)
    page_done = pyqtSignal(int, int)  # 페이지 번호, 누적 건수
    stocks_done = pyqtSignal(list)
    failed = pyqtSignal(str)

    def run(self):
        try:
            self.summary_done.emit(crawl())
            stocks = crawl_stocks(
                progress=lambda page, _count, total: self.page_done.emit(page, total)
            )
            self.stocks_done.emit(stocks)
        except Exception as e:  # 네트워크 오류, 페이지 구조 변경 등
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("코스피200 크롤러")
        self.resize(1180, 860)
        self.setStyleSheet(STYLE_SHEET)

        self.worker = None
        self.summary = None
        self.stocks = []

        root = QWidget(objectName="root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(14)
        self.setCentralWidget(root)

        layout.addLayout(self.build_top_bar())

        # 진행률은 얇은 선으로만 표시하고, 글자는 상단 상태 문구로 보여 줍니다.
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setValue(0)
        policy = self.progress.sizePolicy()
        policy.setRetainSizeWhenHidden(True)  # 숨겨도 자리를 유지해 화면이 들썩이지 않게
        self.progress.setSizePolicy(policy)
        self.progress.hide()
        layout.addWidget(self.progress)

        layout.addWidget(self.build_summary_card())
        layout.addWidget(self.build_stocks_card(), 1)

    # ---------- 화면 구성 ----------

    def build_top_bar(self):
        row = QHBoxLayout()
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(QLabel("코스피200", objectName="appTitle"))
        self.status_label = QLabel("‘데이터 수집’을 눌러 시작하세요", objectName="status")
        texts.addWidget(self.status_label)
        row.addLayout(texts, 1)

        self.crawl_button = self.make_button("데이터 수집", self.start_crawl, "primaryButton")
        self.save_button = self.make_button("CSV 저장", self.save_files)
        self.excel_button = self.make_button("엑셀 저장", self.save_excel)
        self.save_button.setEnabled(False)
        self.excel_button.setEnabled(False)
        for button in (self.save_button, self.excel_button, self.crawl_button):
            row.addWidget(button)
        return row

    def make_button(self, text, slot, name=""):
        button = QPushButton(text, objectName=name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def build_summary_card(self):
        card = QFrame(objectName="card")
        row = QHBoxLayout(card)
        row.setContentsMargins(24, 20, 24, 20)
        row.setSpacing(28)

        # 왼쪽: 지수명 / 현재가 / 등락 — 가장 크게 보여 줍니다.
        head = QVBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(4)
        self.name_label = QLabel("코스피 200", objectName="indexName")
        self.price_label = QLabel("-", objectName="indexPrice")
        self.change_label = QLabel("", objectName="changePill")
        self.change_label.hide()
        self.sub_label = QLabel("", objectName="subInfo")
        head.addWidget(self.name_label)
        head.addWidget(self.price_label)
        head.addWidget(self.change_label, 0, Qt.AlignmentFlag.AlignLeft)
        head.addSpacing(6)
        head.addWidget(self.sub_label)
        head.addStretch()
        head_box = QWidget()
        head_box.setLayout(head)
        head_box.setFixedWidth(250)
        row.addWidget(head_box)

        # 오른쪽: 숫자 타일 2줄
        grid = QGridLayout()
        grid.setSpacing(8)
        self.stat_labels = {}
        for i, (key, title) in enumerate(SUMMARY_TILES):
            tile = QFrame(objectName="tile")
            box = QVBoxLayout(tile)
            box.setContentsMargins(14, 10, 14, 10)
            box.setSpacing(2)
            box.addWidget(QLabel(title, objectName="tileKey"))
            value = QLabel("-", objectName="tileValue")
            box.addWidget(value)
            self.stat_labels[key] = value
            grid.addWidget(tile, i // 6, i % 6)
        row.addLayout(grid, 1)
        return card

    def build_stocks_card(self):
        card = QFrame(objectName="card")
        box = QVBoxLayout(card)
        box.setContentsMargins(20, 16, 20, 12)
        box.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(QLabel("구성종목", objectName="sectionTitle"))
        self.count_badge = QLabel("0개", objectName="count")
        header.addWidget(self.count_badge)
        header.addStretch()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("종목명 또는 종목코드 검색")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(260)
        self.search_edit.textChanged.connect(self.apply_filter)
        header.addWidget(self.search_edit)
        box.addLayout(header)

        self.table = QTableWidget(0, len(STOCK_COLUMNS))
        self.table.setHorizontalHeaderLabels(STOCK_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # 긴 종목명이 잘리지 않게
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.table)
        return card

    # ---------- 수집 ----------

    def start_crawl(self):
        self.crawl_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.excel_button.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.status_label.setText("지수 시세를 가져오는 중...")

        self.worker = CrawlWorker()
        self.worker.summary_done.connect(self.on_summary)
        self.worker.page_done.connect(self.on_page)
        self.worker.stocks_done.connect(self.on_stocks)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(lambda: self.crawl_button.setEnabled(True))
        self.worker.start()

    def on_summary(self, data):
        self.summary = data
        self.name_label.setText(data.get("지수명", "코스피 200"))
        color = sign_color(data.get("전일대비", ""))
        self.price_label.setText(data.get("현재가", "-"))
        self.price_label.setStyleSheet(f"color: {color};")
        arrow = "▲" if color == RISE_COLOR else "▼" if color == FALL_COLOR else ""
        self.change_label.setText(f"{arrow} {data.get('전일대비', '')}   {data.get('등락률(%)', '')}%")
        self.change_label.setStyleSheet(f"color: {color}; background: {PILL_BACKGROUND[color]};")
        self.change_label.show()
        self.sub_label.setText(
            f"52주 {data.get('52주 최저', '-')} ~ {data.get('52주 최고', '-')}\n기준일 {data.get('기준일', '')}"
        )

        for key, label in self.stat_labels.items():
            value = data.get(key, "-")
            label.setText(value)
            if key in SIGNED_TILES:
                label.setStyleSheet(f"color: {sign_color(value)};")
        self.stat_labels["등락종목_상승"].setStyleSheet(f"color: {RISE_COLOR};")
        self.stat_labels["등락종목_하락"].setStyleSheet(f"color: {FALL_COLOR};")
        self.status_label.setText("구성종목을 가져오는 중...")

    def on_page(self, page, total):
        self.progress.setMaximum(max(self.progress.maximum(), total))
        self.progress.setValue(total)
        self.status_label.setText(f"구성종목을 가져오는 중... {page}페이지 · {total}건")

    def on_stocks(self, stocks):
        self.stocks = stocks
        self.fill_table()
        self.progress.setMaximum(max(len(stocks), 1))
        self.progress.setValue(len(stocks))
        self.progress.hide()
        self.status_label.setText(f"{self.summary.get('수집시각', '')} 수집 완료 · 구성종목 {len(stocks)}건")
        self.save_button.setEnabled(True)
        self.excel_button.setEnabled(True)

    def on_failed(self, message):
        self.progress.hide()
        self.status_label.setText("수집에 실패했습니다. 다시 시도해 주세요.")
        QMessageBox.warning(self, "수집 실패", f"데이터를 가져오지 못했습니다.\n\n{message}")

    def fill_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.stocks))
        for row, stock in enumerate(self.stocks):
            color = QColor(sign_color(stock["전일대비"]))
            for col, key in enumerate(STOCK_COLUMNS):
                text = str(stock[key])
                item = NumericItem(text) if key in NUMERIC_COLUMNS else QTableWidgetItem(text)
                if key in NUMERIC_COLUMNS:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if key in SIGNED_COLUMNS or key == "현재가":
                    item.setForeground(color)
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        # Qt 기본 정렬 표시가 내림차순이라, 처음에는 순위 오름차순으로 맞춰 줍니다.
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.apply_filter()

    def apply_filter(self):
        keyword = self.search_edit.text().strip().lower()
        visible = 0
        for row in range(self.table.rowCount()):
            code = self.table.item(row, 1).text()
            name = self.table.item(row, 2).text().lower()
            hidden = bool(keyword) and keyword not in name and keyword not in code
            self.table.setRowHidden(row, hidden)
            visible += not hidden
        total = self.table.rowCount()
        self.count_badge.setText(f"{visible}개" if visible == total else f"{visible} / {total}개")

    # ---------- 저장 ----------

    def save_files(self):
        folder = QFileDialog.getExistingDirectory(self, "저장할 폴더 선택")
        if not folder:
            return
        summary_path = f"{folder}/{OUTPUT_CSV}"
        stocks_path = f"{folder}/{STOCKS_CSV}"
        try:
            save_csv(self.summary, summary_path)
            save_stocks_csv(self.stocks, stocks_path)
        except OSError as e:
            QMessageBox.warning(self, "저장 실패", str(e))
            return
        QMessageBox.information(
            self, "저장 완료",
            f"지수 요약: {summary_path}\n구성종목 {len(self.stocks)}건: {stocks_path}",
        )

    def save_excel(self):
        default_name = f"kospi200_{datetime.now():%Y%m%d_%H%M}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "엑셀로 저장", default_name, "Excel 파일 (*.xlsx)")
        if not path:
            return
        try:
            write_excel(path, self.summary, self.stocks)
        except PermissionError:
            QMessageBox.warning(self, "저장 실패", "파일이 엑셀에서 열려 있는지 확인해 주세요.")
            return
        except OSError as e:
            QMessageBox.warning(self, "저장 실패", str(e))
            return
        QMessageBox.information(self, "저장 완료", f"구성종목 {len(self.stocks)}건과 지수 요약을 저장했습니다.\n{path}")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.wait(3000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
