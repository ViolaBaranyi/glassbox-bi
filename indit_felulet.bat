@echo off
rem Uvegdoboz BI - a BI-felulet inditasa Windowson (dupla kattintassal is mukodik).
rem A bongeszoben nyilik meg: http://localhost:8501   Leallitas: Ctrl+C, vagy zard be ezt az ablakot.
rem A kornyezetet a uv kezeli (uv run): az elso inditaskor letrehozza a rogzitett csomagokkal,
rem kesobb ellenorzi, es ha kell, helyrehozza. Virtualis kornyezetre itt nincs hivatkozas.
cd /d "%~dp0"
rem A uv telepitoje ide teszi a uv-t; ha az ablak a telepites elott nyilt, a PATH-ban meg nincs benne.
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 goto nincs_uv
uv run python -m ui %*
if errorlevel 1 pause
exit /b

:nincs_uv
echo.
echo A uv nincs telepitve ezen a gepen. Telepites: README, Gyorsinditas
echo (egyetlen PowerShell-parancs). Utana inditsd ujra ezt a fajlt.
echo.
pause
exit /b 1
