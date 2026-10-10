@echo off
rem Wielerbulletin: pusht nieuwe afleveringen die de geplande Claude-taak in episodes\ heeft gezet.
rem Draait via Windows Taakplanner elke 5 minuten tussen 07:30 en 09:00. Doet niets als er niets nieuws is.
rem Logboek: pc_push.log in de hoofdmap van de repo.
setlocal
cd /d "%~dp0.."
set LOG=pc_push.log

rem 1. Nieuwe of gewijzigde afleveringen committen (alleen episodes\*.md)
git status --porcelain -- episodes | findstr /r "\.md$" >nul
if not errorlevel 1 (
  echo %date% %time%  nieuwe aflevering gevonden>>%LOG%
  git add -- "episodes/*.md" >>%LOG% 2>&1
  git commit -q -m "Aflevering via pc" >>%LOG% 2>&1
)

rem 2. Niets te pushen? Dan klaar.
set AHEAD=0
for /f %%n in ('git rev-list --count origin/main..HEAD 2^>nul') do set AHEAD=%%n
if "%AHEAD%"=="0" exit /b 0

rem 3. Pushen, maximaal drie pogingen
for /l %%i in (1,1,3) do (
  git pull -q --rebase --autostash origin main >>%LOG% 2>&1
  git push -q origin main >>%LOG% 2>&1 && goto ok
  timeout /t 20 /nobreak >nul
)
echo %date% %time%  PUSH MISLUKT>>%LOG%
exit /b 1

:ok
echo %date% %time%  push gelukt>>%LOG%
exit /b 0
