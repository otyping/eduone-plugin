@echo off
REM eduone-py - รุ่นสำหรับ cmd/PowerShell บน Windows (ไม่มี Git Bash ก็ใช้ได้)
REM ตรรกะเดียวกับไฟล์ eduone-py ข้าง ๆ  ดูคำอธิบายเต็มที่นั่น
setlocal
set "PLUGIN_ROOT=%~dp0.."
if not defined PYTHONIOENCODING set "PYTHONIOENCODING=utf-8"

set "PY="
if defined EDUONE_PYTHON if exist "%EDUONE_PYTHON%" set "PY=%EDUONE_PYTHON%"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY (
  py -3.12 -c "pass" >nul 2>&1 && set "PY=py -3.12"
)
if not defined PY (
  echo eduone-py: ไม่พบ Python 3.12 - ติดตั้งก่อน หรือตั้ง EDUONE_PYTHON 1>&2
  exit /b 1
)

if "%~1"=="" (
  echo eduone-py: ต้องบอกชื่อสคริปต์ เช่น  eduone-py paths.py p4 sci 3 1>&2
  exit /b 1
)
REM อาร์กิวเมนต์แรกขึ้นต้นด้วย - คือตัวเลือกของ python เอง (-m, -c) ส่งต่อตรง ๆ
echo %~1| findstr /b /c:"-" >nul && (
  %PY% %*
  exit /b %errorlevel%
)
set "NAME=%~1"
shift

set "SCRIPT="
if exist "%NAME%" set "SCRIPT=%NAME%"
if not defined SCRIPT if exist "%PLUGIN_ROOT%\skills\shared\scripts\%NAME%" set "SCRIPT=%PLUGIN_ROOT%\skills\shared\scripts\%NAME%"
if not defined SCRIPT for /d %%D in ("%PLUGIN_ROOT%\skills\*") do if exist "%%D\scripts\%NAME%" set "SCRIPT=%%D\scripts\%NAME%"
if not defined SCRIPT (
  echo eduone-py: ไม่พบสคริปต์ "%NAME%" ในปลั๊กอิน 1>&2
  exit /b 1
)

set "ARGS="
:loop
if "%~1"=="" goto run
set "ARGS=%ARGS% "%~1""
shift
goto loop
:run
%PY% "%SCRIPT%"%ARGS%
