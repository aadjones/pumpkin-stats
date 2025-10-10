@echo off
REM Always run from this script's directory
cd /d "%~dp0"

REM Run your existing script's dev target
call run.bat dev

REM Keep window open so they can read output
pause
