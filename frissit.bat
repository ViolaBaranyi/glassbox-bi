@echo off
rem Uvegdoboz BI - a kornyezet frissitese es a tesztek Windowson (dupla kattintassal is mukodik).
rem 1. ha nincs uv, telepiti (ugyanaz a parancs, mint a README Gyorsinditas reszeben);
rem 2. uv sync: a rogzitett csomagok (uv.lock) - egy git pull vagy frissites utan kell;
rem 3. a teljes tesztsor. Minden kimenet a logs\frissites.log fajlba kerul.
rem Commitolni es pusholni nem fog: azt te dontod el.
cd /d "%~dp0"
if not exist logs mkdir logs
set "LOG=logs\frissites.log"
echo Frissites kezdete: %date% %time% > "%LOG%"
rem a regi, aktivalt kornyezet ne zavarjon (a uv a projekt sajat .venv mappajat hasznalja)
set "VIRTUAL_ENV="
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if not errorlevel 1 goto van_uv
echo [0/2] A uv nincs telepitve - telepites (egyszer, nehany masodperc)...
echo --- uv telepitese >> "%LOG%"
powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" >> "%LOG%" 2>&1
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 goto hiba

:van_uv
echo [1/2] uv sync - a rogzitett csomagok (az elso alkalommal par perc)...
echo --- uv sync >> "%LOG%"
uv sync >> "%LOG%" 2>&1
if errorlevel 1 goto hiba
echo [2/2] tesztek (nehany perc)...
echo --- tesztek >> "%LOG%"
uv run python -m pytest -q -p no:cacheprovider >> "%LOG%" 2>&1
if errorlevel 1 goto hiba
echo Frissites vege: %date% %time% - minden rendben >> "%LOG%"
echo.
echo Kesz, minden rendben. A felulet: indit_felulet.bat
powershell -NoProfile -c "Get-Content '%LOG%' -Tail 3"
echo.
pause
exit /b 0

:hiba
echo Frissites vege: %date% %time% - HIBA >> "%LOG%"
echo.
echo Valami nem sikerult. A naplo vege (a teljes: %LOG%):
powershell -NoProfile -c "Get-Content '%LOG%' -Tail 25"
echo.
pause
exit /b 1
