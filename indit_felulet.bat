@echo off
rem Uvegdoboz BI - a BI-felulet inditasa Windowson (dupla kattintassal is mukodik).
rem A bongeszoben nyilik meg: http://localhost:8501   Leallitas: Ctrl+C, vagy zard be ezt az ablakot.
rem A projekt virtualis kornyezetet hasznalja (.venv-1, ennek hianyaban .venv), kulonben a python-t.
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if exist ".venv-1\Scripts\python.exe" set "PY=.venv-1\Scripts\python.exe"
"%PY%" -m ui %*
if errorlevel 1 (
    echo.
    echo A felulet nem indult el. Ha a streamlit hianyzik, telepitsd a rogzitett csomagokat:
    echo     "%PY%" -m pip install -r requirements.lock
    pause
)
