@echo off
title SIAM - Version Online (Flask + PWA)
color 0B
echo ============================================================
echo   SIAM - Aluminios Cristales Villegas
echo   VERSION ONLINE - Servidor Web Flask + PWA Movil
echo ============================================================
echo.
cd /d "%~dp0"

if exist "..\SIAM_Local\venv\Scripts\python.exe" (
    echo Usando entorno virtual de SIAM_Local...
    echo Iniciando servidor Flask en http://localhost:5000
    "..\SIAM_Local\venv\Scripts\python.exe" app.py
    goto :end
)

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    echo Usando Python 3.11 del usuario...
    echo Iniciando servidor Flask en http://localhost:5000
    "%LocalAppData%\Programs\Python\Python311\python.exe" app.py
    goto :end
)

echo Iniciando servidor Flask en http://localhost:5000
python app.py

:end
pause
