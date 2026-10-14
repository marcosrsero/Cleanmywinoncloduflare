@echo off
REM ====================================================
REM  Inicia CleanMyWin (necesita Python instalado)
REM ====================================================
cd /d "%~dp0"
py main.py
if errorlevel 1 (
    echo.
    echo Hubo un problema al iniciar. Instala las librerias con:
    echo    py -m pip install --user customtkinter send2trash
    echo.
    pause
)
