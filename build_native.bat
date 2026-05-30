@echo off
echo =========================================
echo Building Frontend for Native App
echo =========================================

cd frontend
echo Running npm install...
call npm install
echo Running npm run build...
call npm run build

cd ..
echo Frontend build complete. Files are in frontend/dist.
pause
