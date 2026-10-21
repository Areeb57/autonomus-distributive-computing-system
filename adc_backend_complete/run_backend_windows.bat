@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Creating Python virtual environment...
  py -m venv .venv
  if errorlevel 1 goto error
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto error
python -m pip install -r requirements.txt
if errorlevel 1 goto error
set ADC_BACKEND_DB=%~dp0adc_backend.sqlite3
 echo.
echo Starting ADC backend at http://127.0.0.1:8000
 echo API docs: http://127.0.0.1:8000/docs
 echo Press Ctrl+C to stop.
python -m uvicorn main:app --host 127.0.0.1 --port 8000
if errorlevel 1 goto error
goto end
:error
echo.
echo Backend setup or startup failed. Read the error above.
pause
:end
endlocal
