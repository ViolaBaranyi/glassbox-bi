@echo off
rem K1 v1 kiegeszites: a qwen3.5:9b az elso lezart kerdessoron (eval\meresi_kerdessor.toml), a v3 koddal
rem (commit f5db169, ujjlenyomat db97e252...) - ugyanugy, mint az elso meres 4B es 2B futasa, a laptop processzoran.
rem A v3 kodhoz nem nyul: git worktree (v3_kod\), a v3 commit valtozatlanul; melle csak a protokoll
rem (docs\k1_protokoll_v1_9b.json -> v3_kod\docs\k1_protokoll.json) es a tarhaz kerul.
rem   tools\v1_9b_futtatas.bat                               - a meres (a processzoron kb. 8-10 ora)
rem   tools\v1_9b_futtatas.bat --folytat logs\meres\MAPPA    - megszakadt meres folytatasa (a v3_kod mappaban)
cd /d "%~dp0\.."
set "VIRTUAL_ENV="
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
git ls-files --error-unmatch docs\k1_protokoll_v1_9b.json >nul 2>&1
if errorlevel 1 goto nincs_commit
git diff --quiet HEAD -- docs\k1_protokoll_v1_9b.json
if errorlevel 1 goto nincs_commit
git worktree prune
if not exist v3_kod\ git worktree add v3_kod f5db16915e45a111ac7b1c4adb6665c505b8352d
if errorlevel 1 goto hiba
copy /y docs\k1_protokoll_v1_9b.json v3_kod\docs\k1_protokoll.json >nul
if not exist v3_kod\data\warehouse.duckdb copy /y data\warehouse.duckdb v3_kod\data\ >nul
cd v3_kod
uv sync
if errorlevel 1 goto hiba
uv run python -m narrative.meres --modell qwen3.5:9b %*
exit /b %errorlevel%
:nincs_commit
echo A protokoll (docs\k1_protokoll_v1_9b.json) meg nincs commitolva: elobb git add + git commit, utana ujra.
exit /b 1
:hiba
echo HIBA - a v3 munkamappa nem allt ossze (lasd fent).
exit /b 1
