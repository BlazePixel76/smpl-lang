@echo off
where py >nul 2>&1
if %ERRORLEVEL% == 0 (
    py "%~dp0smpl.py" %*
) else (
    python "%~dp0smpl.py" %*
)
