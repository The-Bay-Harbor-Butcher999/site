@echo off
chcp 65001 > nul
echo ===================================================
echo   Запуск АИС "Учёт занятий автошколы" (ООО Драйв)
echo ===================================================

if not exist venv (
    echo [1/4] Создание виртуального окружения...
    py -m venv venv || python -m venv venv
)

echo [2/4] Активация окружения и установка библиотек...
call venv\Scripts\activate
pip install --no-index --find-links=packages -r requirements.txt || pip install -r requirements.txt

echo [3/4] Проверка базы данных и тестовых данных...
python manage.py migrate
python manage.py init_demo

echo [4/4] Запуск веб-сервера! Откройте в браузере: http://127.0.0.1:8000
start http://127.0.0.1:8000
python manage.py runserver
pause
