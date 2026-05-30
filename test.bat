@echo off & setlocal enabledelayedexpansion & set PY=backend\venv\Scripts\pythonw.exe & %%PY%% -x " "%%~f0 %%* & exit /b !ERRORLEVEL!  
import sys  
open('poly_succ', 'w').write('success')  
