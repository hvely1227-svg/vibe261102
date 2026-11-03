"""
대한민국 출생아수·합계출산율 분석 GUI (PyQt6)

birth_analysis.py 의 클렌징/분석 함수와 birth_plot.py 의 차트 함수를 그대로 사용해서
KOSIS 엑셀을 열고, 연도 구간과 지표를 골라 그래프와 분석 결과를 화면에 보여 줍니다.

필요 패키지:
    pip install pandas openpyxl matplotlib PyQt6
"""

import contextlib
import io
import numbers
import sys
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from birth_analysis import (
    COLUMNS,
    DEFAULT_XLSX,
    analyze,
    decade_summary,
    declining_streaks,
    load_and_clean,
    milestones,
    yoy_table,
)
from birth_plot import METRICS, draw_births_vs_deaths, draw_metric

UP_COLOR = "#16A34A"
DOWN_COLOR = "#DC2626"
BIRTHS_VS_DEATHS = "출생아수 vs 사망자수"

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
# 바탕화면 원본이 없으면 저장소 루트에 있는 사본을 연다
CANDIDATE_XLSX = [DEFAULT_XLSX, APP_DIR.parent / DEFAULT_XLSX.name]

DEFAULT_START, DEFAULT_END = 1970, 2025

# 상단 요약 카드: (키, 표시 이름)
SUMMARY_TILES = [
    ("start", "시작 출생아수"),
    ("end", "종료 출생아수"),
    ("change", "구간 변화율"),
    ("max", "최다 출생"),
    ("min", "최소 출생"),
    ("tfr", "종료 합계출산율"),
]

# 쉼표 없이 그대로 보여 줄 연도 컬럼
YEAR_COLS = {"연도", "시작", "종료", "처음 해당 연도"}


def format_value(col: str, val) -> str:
    if val is None or val is pd.NA or (isinstance(val, float) and val != val):
        return "-"
    if isinstance(val, bool):
        return "예" if val else ""
    if col in YEAR_COLS or isinstance(val, str):
        return str(val)
    if isinstance(val, numbers.Integral) or float(val).is_integer():
        return f"{val:,.0f}"
    return f"{val:,.3f}".rstrip("0").rstrip(".")


def fill_table(table: QTableWidget, df: pd.DataFrame, signed_cols=()) -> None:
    """DataFrame 을 QTableWidget 에 채운다. 인덱스는 첫 번째 열로 넣는다."""
    df = df.reset_index() if df.index.name else df
    table.clear()
    table.setRowCount(len(df))
    table.setColumnCount(len(df.columns))
    table.setHorizontalHeaderLabels([str(c) for c in df.columns])
    for r, row in enumerate(df.itertuples(index=False)):
        for c, val in enumerate(row):
            col = df.columns[c]
            item = QTableWidgetItem(format_value(col, val))
            is_num = isinstance(val, numbers.Number) and not isinstance(val, bool)
            if is_num and col not in YEAR_COLS:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col in signed_cols and is_num and val == val:
                if val > 0:
                    item.setForeground(QColor(UP_COLOR))
                elif val < 0:
                    item.setForeground(QColor(DOWN_COLOR))
            table.setItem(r, c, item)
    table.setCurrentItem(None)   # 기본 선택 셀이 색상 글자를 가리지 않도록
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)


def make_table() -> QTableWidget:
    t = QTableWidget()
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    return t


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("대한민국 출생아수 분석")
        self.resize(1280, 820)
        self.df: pd.DataFrame | None = None
        self.clean_log = ""

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addLayout(self._build_toolbar())
        layout.addWidget(self._build_summary())
        layout.addWidget(self._build_tabs(), 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("KOSIS 엑셀 파일을 열어 주세요.")

        for path in CANDIDATE_XLSX:
            if path.exists():
                self.load_xlsx(path)
                break

    # ------------------------------------------------------------ UI 구성
    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("엑셀 파일 경로")
        open_btn = QPushButton("엑셀 열기")
        open_btn.clicked.connect(self.on_open)

        self.start_spin = QSpinBox()
        self.end_spin = QSpinBox()
        for spin, val in ((self.start_spin, DEFAULT_START), (self.end_spin, DEFAULT_END)):
            spin.setRange(1900, 2100)
            spin.setValue(val)
            spin.setSuffix("년")

        self.metric_combo = QComboBox()
        self.metric_combo.addItems(list(METRICS) + [BIRTHS_VS_DEATHS])
        self.metric_combo.currentTextChanged.connect(self.redraw_chart)

        apply_btn = QPushButton("기간 적용")
        apply_btn.clicked.connect(self.refresh)
        reset_btn = QPushButton("전체 기간")
        reset_btn.clicked.connect(self.on_reset_range)
        save_btn = QPushButton("차트 PNG 저장")
        save_btn.clicked.connect(self.on_save_png)
        csv_btn = QPushButton("정제 CSV 저장")
        csv_btn.clicked.connect(self.on_save_csv)

        bar.addWidget(open_btn)
        bar.addWidget(self.path_edit, 1)
        bar.addSpacing(12)
        bar.addWidget(QLabel("시작"))
        bar.addWidget(self.start_spin)
        bar.addWidget(QLabel("종료"))
        bar.addWidget(self.end_spin)
        bar.addWidget(apply_btn)
        bar.addWidget(reset_btn)
        bar.addSpacing(12)
        bar.addWidget(QLabel("지표"))
        bar.addWidget(self.metric_combo)
        bar.addSpacing(12)
        bar.addWidget(save_btn)
        bar.addWidget(csv_btn)
        return bar

    def _build_summary(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        row = QHBoxLayout(frame)
        self.tiles: dict[str, QLabel] = {}
        self.tile_notes: dict[str, QLabel] = {}
        for key, name in SUMMARY_TILES:
            box = QVBoxLayout()
            title = QLabel(name)
            title.setStyleSheet("color: #6B7280;")
            value = QLabel("-")
            font = QFont()
            font.setPointSize(15)
            font.setBold(True)
            value.setFont(font)
            note = QLabel("")
            note.setStyleSheet("color: #6B7280;")
            box.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
            box.addWidget(value, alignment=Qt.AlignmentFlag.AlignCenter)
            box.addWidget(note, alignment=Qt.AlignmentFlag.AlignCenter)
            row.addLayout(box)
            self.tiles[key] = value
            self.tile_notes[key] = note
        return frame

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        chart = QWidget()
        v = QVBoxLayout(chart)
        self.figure = Figure(figsize=(12, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        v.addWidget(NavigationToolbar2QT(self.canvas, chart))
        v.addWidget(self.canvas, 1)
        tabs.addTab(chart, "추이 차트")

        self.decade_table = make_table()
        self.yoy_table = make_table()
        self.streak_table = make_table()
        self.milestone_table = make_table()
        self.corr_table = make_table()
        self.data_table = make_table()
        tabs.addTab(self.decade_table, "연대별 요약")
        tabs.addTab(self.yoy_table, "전년 대비 증감")
        tabs.addTab(self.streak_table, "연속 감소 구간")
        tabs.addTab(self.milestone_table, "주요 이정표")
        tabs.addTab(self.corr_table, "상관계수")
        tabs.addTab(self.data_table, "정제 데이터")

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 10))
        tabs.addTab(self.log, "클렌징·분석 로그")
        return tabs

    # ------------------------------------------------------------ 동작
    def on_open(self):
        start_dir = next((p.parent for p in CANDIDATE_XLSX if p.exists()), APP_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self, "KOSIS 출생 통계 엑셀 선택", str(start_dir), "엑셀 파일 (*.xlsx *.xls)")
        if path:
            self.load_xlsx(Path(path))

    def load_xlsx(self, path: Path):
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                df = load_and_clean(path)
        except Exception as e:
            QMessageBox.critical(self, "불러오기 실패", f"{path}\n\n{e}")
            return
        if df.empty or "출생아수" not in df:
            QMessageBox.warning(self, "데이터 없음", "출생아수 데이터를 찾지 못했습니다.")
            return

        self.df = df
        self.clean_log = buf.getvalue()
        self.path_edit.setText(str(path))

        lo, hi = int(df.index.min()), int(df.index.max())
        for spin in (self.start_spin, self.end_spin):
            spin.setRange(lo, hi)
        self.start_spin.setValue(max(lo, DEFAULT_START))
        self.end_spin.setValue(min(hi, DEFAULT_END))

        fill_table(self.data_table, df.sort_index(ascending=False),
                   signed_cols=("자연증가", "자연증가율", "출생아_증감", "출생아_증감률%"))
        self.refresh()

    def on_reset_range(self):
        if self.df is None:
            return
        self.start_spin.setValue(self.start_spin.minimum())
        self.end_spin.setValue(self.end_spin.maximum())
        self.refresh()

    def selected(self) -> pd.DataFrame | None:
        if self.df is None:
            return None
        start, end = self.start_spin.value(), self.end_spin.value()
        sub = self.df.loc[start:end]
        if len(sub) < 2:
            QMessageBox.warning(self, "기간 오류", "시작 연도가 종료 연도보다 앞서야 하고, 2년 이상이어야 합니다.")
            return None
        return sub

    def redraw_chart(self):
        sub = self.selected() if self.df is not None else None
        if sub is None:
            return
        start, end = int(sub.index.min()), int(sub.index.max())
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        metric = self.metric_combo.currentText()
        if metric == BIRTHS_VS_DEATHS:
            draw_births_vs_deaths(ax, self.df, start, end)
        else:
            draw_metric(ax, self.df, metric, start, end)
        self.canvas.draw_idle()

    def refresh(self):
        sub = self.selected()
        if sub is None:
            return
        start, end = int(sub.index.min()), int(sub.index.max())
        self.redraw_chart()

        # 요약 카드
        b = sub["출생아수"]
        change = (b.iloc[-1] / b.iloc[0] - 1) * 100
        prelim = " (잠정)" if sub["잠정치"].iloc[-1] else ""
        cards = {
            "start": (f"{b.iloc[0]:,}명", f"{start}년"),
            "end": (f"{b.iloc[-1]:,}명", f"{end}년{prelim}"),
            "change": (f"{change:+.1f}%", f"{start}→{end}"),
            "max": (f"{b.max():,}명", f"{b.idxmax()}년"),
            "min": (f"{b.min():,}명", f"{b.idxmin()}년"),
            "tfr": (f"{sub['합계출산율'].iloc[-1]:.3f}명", f"{end}년{prelim}"),
        }
        for key, (value, note) in cards.items():
            self.tiles[key].setText(value)
            self.tile_notes[key].setText(note)
        self.tiles["change"].setStyleSheet(f"color: {UP_COLOR if change >= 0 else DOWN_COLOR};")

        # 분석 표
        fill_table(self.decade_table, decade_summary(sub), signed_cols=("자연증가 합계",))
        fill_table(self.yoy_table, yoy_table(sub).sort_index(ascending=False),
                   signed_cols=("출생아_증감", "출생아_증감률%"))
        fill_table(self.streak_table, declining_streaks(sub), signed_cols=("누적감소",))
        ms = pd.DataFrame(milestones(sub), columns=["기준", "처음 해당 연도"])
        ms["처음 해당 연도"] = ms["처음 해당 연도"].map(lambda y: y if y else "구간 내 없음")
        fill_table(self.milestone_table, ms)
        cols = list(COLUMNS.values()) + ["사망자수"]
        corr = sub[cols].astype(float).corr().round(3)
        corr.index.name = "지표"
        fill_table(self.corr_table, corr, signed_cols=cols)

        # 텍스트 로그 (스크립트와 동일한 출력)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            analyze(sub)
        self.log.setPlainText(self.clean_log + "\n" + buf.getvalue())

        self.statusBar().showMessage(f"{start}~{end}년  ·  {len(sub)}개 연도  ·  전체 {len(self.df)}행")

    def on_save_png(self):
        if self.df is None:
            return
        name = f"{self.metric_combo.currentText().replace(' ', '_')}_{self.start_spin.value()}_{self.end_spin.value()}.png"
        path, _ = QFileDialog.getSaveFileName(self, "차트 저장", str(APP_DIR / name), "PNG 이미지 (*.png)")
        if path:
            self.figure.savefig(path, dpi=150)
            self.statusBar().showMessage(f"차트 저장: {path}")

    def on_save_csv(self):
        if self.df is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "정제 데이터 저장", str(APP_DIR / "birth_cleaned.csv"), "CSV 파일 (*.csv)")
        if path:
            self.df.to_csv(path, encoding="utf-8-sig")
            self.statusBar().showMessage(f"CSV 저장: {path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 9))   # 한글 폰트 (Windows)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
