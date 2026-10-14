@echo off
REM ====================================================
REM  Crea CleanMyWin.exe (un unico archivo ejecutable)
REM  No necesitaras Python para usarlo despues.
REM ====================================================
cd /d "%~dp0"
echo Instalando PyInstaller (si hace falta)...
py -m pip install --user pyinstaller
echo.
echo Creando el ejecutable, espera un momento...
py -m PyInstaller --noconfirm --onefile --windowed --name "CleanMyWin" ^
   --collect-all customtkinter main.py
echo.
echo ====================================================
echo  Listo. El ejecutable esta en la carpeta:  dist\CleanMyWin.exe
echo ====================================================
pause
