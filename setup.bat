@echo off
echo =========================================
echo Setting up Meeting Recorder on Windows
echo =========================================

echo 1. Installing Frontend Dependencies and compiling...
cd frontend
call npm install
call npm run build
cd ..

echo 2. Setting up Python Virtual Environment...
cd backend
if exist venv rmdir /s /q venv
python -m venv venv
call .\venv\Scripts\activate
echo Installing Python dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
cd ..

echo =========================================
echo Setup Complete!
echo Double-click 'Launch.vbs' in the root to run the application.
echo =========================================
pause
