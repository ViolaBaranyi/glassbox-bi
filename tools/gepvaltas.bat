@echo off
rem K1 gephatas (docs\k1_protokoll_gepvaltas.json) - minden gepen ugyanaz a parancs.
rem   tools\gepvaltas.bat felvesz GEP        - a gep felvetele (egyszer, az elso futasa elott; utana commit + push)
rem   tools\gepvaltas.bat GEP                - a gepen meg hianyzo futasok egymas utan; ha felbeszakad, ugyanez folytatja
rem   tools\gepvaltas.bat GEP --allapot      - mi van meg, mi hianyzik
rem   tools\gepvaltas.bat GEP --csak m1-4b   - csak a megadott par(ok)
rem A reszletek: tools\gepvaltas_futtat.py. A laptopon a protokoll szerint nincs uj futas.
setlocal
cd /d "%~dp0\.."
set "VIRTUAL_ENV="
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
set "PYTHONUTF8=1"
uv run python tools\gepvaltas_futtat.py %*
exit /b %errorlevel%
