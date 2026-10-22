@echo off
rem A gep adatai a helyi nyelvi modellhez: videokartya, processzor, memoria, Ollama es a
rem letoltott modellek, uv, git. Semmit nem telepit es nem modosit; az eredmeny:
rem logs\gep_ellenorzes.txt (a logs mappa nem kerul a taroloba).
rem   tools\gep_ellenorzes.bat
cd /d "%~dp0\.."
if not exist logs mkdir logs
set "OUT=logs\gep_ellenorzes.txt"
if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"

echo Gep ellenorzes: %COMPUTERNAME%, %date% %time%> "%OUT%"
echo.>> "%OUT%"
echo == Videokartya (nvidia-smi)>> "%OUT%"
where nvidia-smi >> "%OUT%" 2>&1 && nvidia-smi >> "%OUT%" 2>&1
echo.>> "%OUT%"
echo == Videokartyak (Windows)>> "%OUT%"
powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, VideoProcessor | Format-List | Out-String -Width 200" >> "%OUT%" 2>&1
echo == Processzor es memoria>> "%OUT%"
powershell -NoProfile -Command "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors | Format-List | Out-String -Width 200; '{0:N1} GB RAM' -f ((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)" >> "%OUT%" 2>&1
echo.>> "%OUT%"
echo == Ollama>> "%OUT%"
where ollama >> "%OUT%" 2>&1
ollama --version >> "%OUT%" 2>&1
echo -- letoltott modellek (ollama list):>> "%OUT%"
ollama list >> "%OUT%" 2>&1
echo -- betoltott modellek (ollama ps):>> "%OUT%"
ollama ps >> "%OUT%" 2>&1
echo.>> "%OUT%"
echo == uv es Python>> "%OUT%"
uv --version >> "%OUT%" 2>&1
python --version >> "%OUT%" 2>&1
echo.>> "%OUT%"
echo == git>> "%OUT%"
git log -1 --format="%%H %%ci %%s" >> "%OUT%" 2>&1
git status --short >> "%OUT%" 2>&1

type "%OUT%"
echo.
echo Kesz: %OUT%
pause
