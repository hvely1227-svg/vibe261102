"""
S&P 500 과거 데이터 분석 GUI (PyQt6)

sp500_analysis.py 의 클렌징/분석/차트 함수를 그대로 사용해서
CSV 를 열고, 기간을 골라 종가 그래프와 분석 결과를 화면에 보여 줍니다.

필요 패키지:
    pip install pandas matplotlib PyQt6
"""

import contextlib
import io
import sys
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDateEdit,
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
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sp500_analysis import (
    DEFAULT_CSV,
    analyze,
    draw_close,
    load_and_clean,
    ma_crosses,
    monthly_seasonality,
    performance,
    weekday_returns,
    yearly_summary,
)

# 미국 증시 관례: 상승은 초록, 하락은 빨강
RISE_COLOR = "#16A34A"
FALL_COLOR = "#DC2626"

# PyInstaller 로 묶인 exe 에서는 __file__ 이 임시 폴더를 가리키므로
# 리소스는 _MEIPASS 에서, 저장 기본 위치는 exe 가 있는 폴더를 쓴다
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent

DEFAULT_START = QDate(2000, 1, 1)
DEFAULT_END = QDate(2019, 12, 31)

# 상단 요약 카드: (키, 표시 이름)
SUMMARY_TILES = [
    ("start", "시작 종가"),
    ("end", "종료 종가"),
    ("total_pct", "누적 수익률"),
    ("cagr_pct", "연평균(CAGR)"),
    ("vol_pct", "연환산 변동성"),
    ("mdd_pct", "최대 낙폭(MDD)"),
]


def fill_table(table: QTableWidget, df: pd.DataFrame, signed_cols=()) -> None:
    """DataFrame 을 QTableWidget 에 채운다. 인덱스는 첫 번째 열로 넣는다."""
    df = df.reset_index()
    table.clear()
    table.setRowCount(len(df))
    table.setColumnCount(len(df.columns))
    table.setHorizontalHeaderLabels([str(c) for c in df.columns])
    for r, row in enumerate(df.itertuples(index=False)):
        for c, val in enumerate(row):
            col = df.columns[c]
            if isinstance(val, pd.Timestamp):
                text = f"{val:%Y-%m-%d}"
            elif isinstance(val, float):
                text = f"{val:,.2f}"
            else:
                text = str(val)
            item = QTableWidgetItem(text)
            if isinstance(val, (int, float)) and c > 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col in signed_cols and isinstance(val, (int, float)) and val == val:
                if val > 0:
                    item.setForeground(QColor(RISE_COLOR))
                elif val < 0:
                    item.setForeground(QColor(FALL_COLOR))
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
        self.setWindowTitle("S&P 500 과거 데이터 분석")
        self.resize(1280, 820)
        self.df: pd.DataFrame | None = None

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addLayout(self._build_toolbar())
        layout.addWidget(self._build_summary())
        layout.addWidget(self._build_tabs(), 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("CSV 파일을 열어 주세요.")

        if DEFAULT_CSV.exists():
            self.load_csv(DEFAULT_CSV)

    # ------------------------------------------------------------ UI 구성
    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("CSV 파일 경로")
        open_btn = QPushButton("CSV 열기")
        open_btn.clicked.connect(self.on_open)

        self.start_edit = QDateEdit(DEFAULT_START)
        self.end_edit = QDateEdit(DEFAULT_END)
        for e in (self.start_edit, self.end_edit):
            e.setCalendarPopup(True)
            e.setDisplayFormat("yyyy-MM-dd")

        apply_btn = QPushButton("기간 적용")
        apply_btn.clicked.connect(self.refresh)
        reset_btn = QPushButton("전체 기간")
        reset_btn.clicked.connect(self.on_reset_range)
        save_btn = QPushButton("차트 PNG 저장")
        save_btn.clicked.connect(self.on_save_png)

        bar.addWidget(open_btn)
        bar.addWidget(self.path_edit, 1)
        bar.addSpacing(12)
        bar.addWidget(QLabel("시작"))
        bar.addWidget(self.start_edit)
        bar.addWidget(QLabel("종료"))
        bar.addWidget(self.end_edit)
        bar.addWidget(apply_btn)
        bar.addWidget(reset_btn)
        bar.addSpacing(12)
        bar.addWidget(save_btn)
        return bar

    def _build_summary(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        row = QHBoxLayout(frame)
        self.tiles: dict[str, QLabel] = {}
        for key, name in SUMMARY_TILES:
            box = QVBoxLayout()
            title = QLabel(name)
            title.setStyleSheet("color: #6B7280;")
            value = QLabel("-")
            font = QFont()
            font.setPointSize(15)
            font.setBold(True)
            value.setFont(font)
            box.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
            box.addWidget(value, alignment=Qt.AlignmentFlag.AlignCenter)
            row.addLayout(box)
            self.tiles[key] = value
        self.mdd_label = QLabel("")
        self.mdd_label.setStyleSheet("color: #6B7280;")
        wrap = QFrame()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(frame)
        v.addWidget(self.mdd_label, alignment=Qt.AlignmentFlag.AlignRight)
        return wrap

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        chart = QWidget()
        v = QVBoxLayout(chart)
        self.figure = Figure(figsize=(12, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        v.addWidget(NavigationToolbar2QT(self.canvas, chart))
        v.addWidget(self.canvas, 1)
        tabs.addTab(chart, "종가 차트")

        self.yearly_table = make_table()
        self.monthly_table = make_table()
        self.weekday_table = make_table()
        self.cross_table = make_table()
        self.data_table = make_table()
        tabs.addTab(self.yearly_table, "연도별 요약")
        tabs.addTab(self.monthly_table, "월별 계절성")
        tabs.addTab(self.weekday_table, "요일별 수익률")
        tabs.addTab(self.cross_table, "골든/데드크로스")
        tabs.addTab(self.data_table, "정제 데이터")

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 10))
        tabs.addTab(self.log, "클렌징·분석 로그")
        return tabs

    # ------------------------------------------------------------ 동작
    def on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "S&P 500 CSV 선택", str(DEFAULT_CSV.parent), "CSV 파일 (*.csv)")
        if path:
            self.load_csv(Path(path))

    def load_csv(self, path: Path):
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                df = load_and_clean(path)
        except Exception as e:
            QMessageBox.critical(self, "불러오기 실패", f"{path}\n\n{e}")
            return
        if df.empty:
            QMessageBox.warning(self, "데이터 없음", "정제 후 남은 데이터가 없습니다.")
            return

        self.df = df
        self.clean_log = buf.getvalue()
        self.path_edit.setText(str(path))

        lo, hi = df.index.min(), df.index.max()
        for e in (self.start_edit, self.end_edit):
            e.setDateRange(QDate(lo.year, lo.month, lo.day), QDate(hi.year, hi.month, hi.day))
        fill_table(self.data_table, df.sort_index(ascending=False)
                   .reset_index().rename(columns={"Date": "날짜", "Close": "종가", "Open": "시가",
                                                  "High": "고가", "Low": "저가",
                                                  "ChangePct": "변동%", "Return": "재계산수익률%"})
                   .set_index("날짜"), signed_cols=("변동%", "재계산수익률%"))
        self.refresh()

    def on_reset_range(self):
        if self.df is None:
            return
        self.start_edit.setDate(self.start_edit.minimumDate())
        self.end_edit.setDate(self.end_edit.maximumDate())
        self.refresh()

    def selected(self) -> pd.DataFrame | None:
        if self.df is None:
            return None
        start = self.start_edit.date().toString("yyyy-MM-dd")
        end = self.end_edit.date().toString("yyyy-MM-dd")
        sub = self.df.loc[start:end]
        if len(sub) < 2:
            QMessageBox.warning(self, "기간 오류", "선택한 기간에 데이터가 2일 이상 있어야 합니다.")
            return None
        return sub

    def refresh(self):
        sub = self.selected()
        if sub is None:
            return
        start, end = sub.index.min(), sub.index.max()

        # 차트: 200일선은 전체 데이터로 계산되도록 원본 df 를 넘긴다
        self.figure.clear()
        draw_close(self.figure.add_subplot(111), self.df, start, end)
        self.canvas.draw_idle()

        # 요약 카드
        p = performance(sub)
        self.tiles["start"].setText(f"{p['start']:,.2f}")
        self.tiles["end"].setText(f"{p['end']:,.2f}")
        for key in ("total_pct", "cagr_pct", "mdd_pct"):
            v = p[key]
            self.tiles[key].setText(f"{v:+.2f}%")
            self.tiles[key].setStyleSheet(f"color: {RISE_COLOR if v >= 0 else FALL_COLOR};")
        self.tiles["vol_pct"].setText(f"{p['vol_pct']:.2f}%")
        rec = f"{p['recovered']:%Y-%m-%d}" if p["recovered"] is not None else "기간 내 미회복"
        self.mdd_label.setText(f"MDD 구간: 고점 {p['mdd_peak']:%Y-%m-%d} → 저점 "
                               f"{p['mdd_trough']:%Y-%m-%d} / 회복 {rec}")

        # 분석 표
        fill_table(self.yearly_table, yearly_summary(sub), signed_cols=("연수익률%",))
        fill_table(self.monthly_table, monthly_seasonality(sub), signed_cols=("평균%", "중앙값%"))
        fill_table(self.weekday_table, weekday_returns(sub), signed_cols=("평균수익률%",))
        cross = ma_crosses(self.df).loc[start:end]   # 이동평균은 전체 데이터 기준
        fill_table(self.cross_table, cross.rename("신호").rename_axis("날짜").to_frame())

        # 텍스트 로그 (스크립트와 동일한 출력)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            analyze(sub)
        self.log.setPlainText(self.clean_log + "\n" + buf.getvalue())

        self.statusBar().showMessage(
            f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}  ·  {len(sub):,}거래일  ·  전체 {len(self.df):,}행")

    def on_save_png(self):
        if self.df is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "차트 저장", str(APP_DIR / "sp500_close.png"), "PNG 이미지 (*.png)")
        if path:
            self.figure.savefig(path, dpi=150)
            self.statusBar().showMessage(f"차트 저장: {path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes

        # 작업 표시줄에 python 아이콘 대신 앱 아이콘이 보이도록
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("sp500.analysis.gui")
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(RESOURCE_DIR / "app.ico")))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
