@echo off
setlocal
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
set "PYTHONPATH=%HERE%\src;%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"
if "%PYTHON%"=="" set "PYTHON=python"
"%PYTHON%" -m wm_maint.mcp_server --model "%HERE%\artifacts\world_model.npz"
endlocal
