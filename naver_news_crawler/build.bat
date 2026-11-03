@echo off
chcp 65001 > nul
REM ============================================================
REM  네이버 뉴스 크롤러 실행 파일(.exe) 빌드 및 배포 파일 생성
REM  결과물: dist\NaverNewsCrawler.exe, release\NaverNewsCrawler_v%VERSION%.zip
REM ============================================================
cd /d "%~dp0"
set VERSION=1.0.0

echo [1/4] 필요한 패키지 설치
python -m pip install requests beautifulsoup4 PyQt6 openpyxl pillow pyinstaller || goto :error

echo [2/4] 아이콘 생성
if not exist app.ico python make_icon.py || goto :error

echo [3/4] PyInstaller로 실행 파일 빌드
REM --onefile   : 하나의 exe 파일로 묶음
REM --windowed  : 실행 시 검은 콘솔 창을 띄우지 않음
REM --add-data  : 창 아이콘으로 쓸 app.ico를 exe 안에 포함
REM --exclude-module : 쓰지 않는 큰 모듈을 빼서 용량 줄이기
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name NaverNewsCrawler ^
    --icon app.ico ^
    --add-data "app.ico;." ^
    --exclude-module tkinter ^
    --exclude-module PIL ^
    --exclude-module numpy ^
    naver_news_gui.py || goto :error

echo [4/4] 배포용 zip 만들기
if not exist release mkdir release
powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\NaverNewsCrawler.exe','배포_안내.txt' -DestinationPath 'release\NaverNewsCrawler_v%VERSION%.zip'" || goto :error

echo.
echo 빌드 완료!
echo   실행 파일 : dist\NaverNewsCrawler.exe
echo   배포 파일 : release\NaverNewsCrawler_v%VERSION%.zip
exit /b 0

:error
echo.
echo 빌드 중 오류가 발생했습니다.
exit /b 1
