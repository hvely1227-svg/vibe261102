@echo off
chcp 65001 > nul
REM ============================================================
REM  S&P 500 분석기 실행 파일(.exe) 빌드
REM  결과물: dist\SP500Analyzer.exe
REM ============================================================
cd /d "%~dp0"

echo [1/3] 필요한 패키지 설치
python -m pip install pandas matplotlib PyQt6 pillow pyinstaller || goto :error

echo [2/3] 아이콘 생성
if not exist app.ico python make_icon.py || goto :error

echo [3/3] PyInstaller로 실행 파일 빌드
REM --onefile   : 하나의 exe 파일로 묶음
REM --windowed  : 실행 시 검은 콘솔 창을 띄우지 않음
REM --add-data  : 창 아이콘으로 쓸 app.ico를 exe 안에 포함
REM --exclude-module : 쓰지 않는 큰 모듈을 빼서 용량 줄이기
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name SP500Analyzer ^
    --icon app.ico ^
    --add-data "app.ico;." ^
    --exclude-module tkinter ^
    --exclude-module IPython ^
    --exclude-module PyQt5 ^
    --exclude-module PySide6 ^
    --exclude-module scipy ^
    --exclude-module openpyxl ^
    --exclude-module bs4 ^
    --exclude-module lxml ^
    sp500_gui.py || goto :error

echo.
echo 빌드 완료!
echo   실행 파일 : dist\SP500Analyzer.exe
exit /b 0

:error
echo.
echo 빌드 중 오류가 발생했습니다.
exit /b 1
