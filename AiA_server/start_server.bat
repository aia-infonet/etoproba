@echo off
chcp 65001 >nul
echo ===============================
echo   Ai Assistant Voice — Server
echo ===============================
echo.

:: Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден. Убедитесь, что Python 3.10+ добавлен в PATH.
    pause
    exit /b 1
)

echo [OK] Python найден:
python --version
echo.

:: Проверяем зависимости
echo [INFO] Проверка зависимостей...
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Установка зависимостей...
    pip install -r requirements.txt
)

:: Запуск сервера
echo [INFO] Запуск сервера...
echo.
cd /d "%~dp0"
python server.py

pause
