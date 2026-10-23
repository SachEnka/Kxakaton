@echo off
chcp 65001 >nul
cd /d "%~dp0"

title Умный кредитный кабинет

echo.
echo  Умный кредитный кабинет — запуск
echo  --------------------------------
echo.

where docker >nul 2>&1
if errorlevel 1 (
  echo  [Ошибка] Docker не найден.
  echo  Установите Docker Desktop и запустите его, затем снова этот файл.
  echo.
  pause
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo  [Ошибка] Docker не запущен.
  echo  Откройте Docker Desktop и дождитесь статуса "Running".
  echo.
  pause
  exit /b 1
)

echo  Собираю и поднимаю контейнеры...
echo  Кабинет:  http://localhost:8080
echo  API/Swagger: http://localhost:8000/docs
echo.
echo  Демо-пароль: Demo-2026
echo  Остановка: Ctrl+C в этом окне, затем Y.
echo.

start "" cmd /c "timeout /t 12 /nobreak >nul & start http://localhost:8080"

docker compose up --build
set EXITCODE=%ERRORLEVEL%

echo.
if not %EXITCODE%==0 (
  echo  [Ошибка] docker compose завершился с кодом %EXITCODE%.
) else (
  echo  Контейнеры остановлены.
)
echo.
pause
exit /b %EXITCODE%
