@echo off
setlocal
cd /d "%~dp0"
E06_Cloud_GUI.exe %*
set EXIT_CODE=%ERRORLEVEL%
echo.
echo E06 Cloud GUI exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
