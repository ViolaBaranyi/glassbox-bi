@echo off
rem A v4 nyelvi reteg (commit e8c8bdda, ujjlenyomat 7a3a5e94...) futtatasa a v3 kerdessoron, kulon
rem munkamappaban (v4_kod\) - igy a v4 es a v5 ugyanazokon a kerdeseken vetheto ossze. A v4 kodhoz nem
rem nyul: git worktree, a commit valtozatlanul; melle csak a v3 kerdessor, a protokoll (a kod-ujjlenyomat
rem a v4-e, tools\v4_protokoll.py) es a tarhaz kerul.
rem   tools\v4_futtatas.bat                               - meres a protokoll elso modelljevel (4B)
rem   tools\v4_futtatas.bat --folytat logs\meres\MAPPA    - megszakadt meres folytatasa (a v4_kod mappaban)
cd /d "%~dp0\.."
set "VIRTUAL_ENV="
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if not exist v4_kod\ git worktree add v4_kod e8c8bdda8f6ee6b193dd1154512fb63fbd2c50da
if errorlevel 1 goto hiba
copy /y eval\meresi_kerdessor_v3.toml v4_kod\eval\ >nul
uv run python tools\v4_protokoll.py v4_kod\docs\k1_protokoll_v3.json
if errorlevel 1 goto hiba
if not exist v4_kod\data\warehouse.duckdb copy /y data\warehouse.duckdb v4_kod\data\ >nul
cd v4_kod
uv sync
if errorlevel 1 goto hiba
uv run python -m narrative.meres --protokoll docs\k1_protokoll_v3.json %*
exit /b %errorlevel%
:hiba
echo HIBA - a v4 munkamappa nem allt ossze (lasd fent).
exit /b 1
