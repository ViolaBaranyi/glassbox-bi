@echo off
rem A v3 nyelvi reteg (a lezart K1 meres kodja, commit f5db169, ujjlenyomat db97e252...) futtatasa az
rem UJ kerdessoron, kulon munkamappaban (v3_kod\) - igy a v3 es a v4 ugyanazokon a kerdeseken vetheto ossze.
rem A v3 kodhoz nem nyul: git worktree, a v3 commit valtozatlanul; csak a v2 protokoll, az uj kerdessor
rem es a tarhaz kerul melle.
rem   tools\v3_futtatas.bat                               - meres a protokoll elso modelljevel
rem   tools\v3_futtatas.bat --folytat logs\meres\MAPPA    - megszakadt meres folytatasa (a v3_kod mappaban)
cd /d "%~dp0\.."
set "VIRTUAL_ENV="
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if not exist v3_kod\ git worktree add v3_kod f5db16915e45a111ac7b1c4adb6665c505b8352d
if errorlevel 1 goto hiba
copy /y eval\meresi_kerdessor_v2.toml v3_kod\eval\ >nul
copy /y docs\k1_protokoll_v2.json v3_kod\docs\k1_protokoll.json >nul
if not exist v3_kod\data\warehouse.duckdb copy /y data\warehouse.duckdb v3_kod\data\ >nul
cd v3_kod
uv sync
if errorlevel 1 goto hiba
uv run python -m narrative.meres %*
exit /b %errorlevel%
:hiba
echo HIBA - a v3 munkamappa nem allt ossze (lasd fent).
exit /b 1
