@echo off
pushd "%~dp0"

echo Running VisualizeLog.py, please wait...

python VisualizeLog.py

rem Python script will print the success message in Chinese.
rem pause command is optional, remove if you want the window to close automatically.
pause