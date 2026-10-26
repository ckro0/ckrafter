@echo off
cd /d "%~dp0"
title Ckrafter

py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 goto no_python

if not exist ".venv\Scripts\python.exe" (
    echo Preparando Ckrafter por primera vez...
    py -3 -m venv .venv
    if errorlevel 1 goto setup_error
)

set "INSTALL_LOG=%TEMP%\ckrafter-install-%RANDOM%.log"
if exist ".venv\.ckrafter-listo" goto dependencies_ready

echo Instalando componentes. Esta preparacion solo se realiza una vez...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --quiet -r requirements.txt > "%INSTALL_LOG%" 2>&1
if errorlevel 1 goto install_error
echo listo>".venv\.ckrafter-listo"
del /q "%INSTALL_LOG%" >nul 2>&1

:dependencies_ready
echo Abriendo tu espacio de trabajo...
start "" ".venv\Scripts\pythonw.exe" -m src.interfaces.web
exit /b

:no_python
echo No se encontro Python 3.11 o posterior.
echo Instala Python desde https://www.python.org/downloads/ y vuelve a intentarlo.
pause
exit /b 1

:setup_error
echo.
echo No se pudo preparar Python. Comprueba la instalacion e intenta de nuevo.
pause
exit /b 1

:install_error
echo.
echo No se pudieron instalar los componentes. Comprueba tu conexion a Internet.
echo Detalle del error:
type "%INSTALL_LOG%"
pause
exit /b 1
