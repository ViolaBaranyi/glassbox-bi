@echo off
rem Uvegdoboz BI - inditas Windowson (dupla kattintassal is mukodik). A macOS/Linux-os parja: indit_felulet.sh
rem 1. ha nincs uv, telepiti (egyszer, nehany masodperc; ugyanaz a parancs, mint a README-ben);
rem 2. a uv a rogzitett valtozatokkal (uv.lock) eloallitja a Python 3.14-et es a csomagokat;
rem 3. az inditas.py elokesziti, ami hianyzik (adat, tarhaz, modellek), es megnyitja a feluletet.
rem A bongeszoben nyilik meg: http://localhost:8501   Leallitas: Ctrl+C, vagy zard be ezt az ablakot.
rem Kapcsolok (pl. csak ellenorzes): indit_felulet.bat --ellenorzes   Az osszes: indit_felulet.bat --help
cd /d "%~dp0"
rem egy regi, aktivalt Python-kornyezet ne zavarjon (a uv a projekt sajatjat hasznalja)
set "VIRTUAL_ENV="
rem A uv telepitoje ide teszi a uv-t; ha az ablak a telepites elott nyilt, a PATH-ban meg nincs benne.
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if not errorlevel 1 goto van_uv
echo A uv nincs telepitve - telepites (egyszer, nehany masodperc)...
powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 goto nincs_uv

:van_uv
uv run python inditas.py %*
if errorlevel 1 pause
exit /b

:nincs_uv
echo.
echo A uv telepitese nem sikerult. Kezi telepites: README, Gyorsinditas
echo (egyetlen PowerShell-parancs). Utana inditsd ujra ezt a fajlt.
echo.
pause
exit /b 1
