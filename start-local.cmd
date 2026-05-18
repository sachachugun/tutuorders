@echo off
cd /d "%~dp0"

if not exist "backend\app.db" (
  echo Initializing database...
  pushd backend
  py init_db.py
  popd
)

echo.
echo tutuorders local
echo   Frontend: http://localhost:5173
echo   Backend:  http://127.0.0.1:8000
echo   Close both windows to stop.
echo.

start "tutuorders-backend" cmd /k cd /d "%~dp0backend" ^&^& py -m uvicorn app.main:app --reload
start "tutuorders-frontend" cmd /k cd /d "%~dp0frontend" ^&^& npm run dev
