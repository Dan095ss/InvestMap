@echo off
setlocal EnableDelayedExpansion

echo.
echo  === InvestMap Launcher ===
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 ( echo [ERROR] Failed to create venv. & pause & exit /b 1 )
)

call .venv\Scripts\activate.bat

echo [2/4] Installing dependencies...
pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 ( echo [ERROR] pip install failed. & pause & exit /b 1 )

if not exist ".env" (
    echo [3/4] Generating SECRET_KEY...
    python -c "import secrets; open('.env','w').write('SECRET_KEY='+secrets.token_hex(32)+'\n')"
) else (
    echo [3/4] .env found.
)

for /f "tokens=1,2 delims==" %%A in (.env) do set %%A=%%B

if not exist "instance\investmap.db" (
    echo [4/4] First run - loading database...
    python seed.py
    if errorlevel 1 ( echo [ERROR] seed.py failed. & pause & exit /b 1 )
) else (
    echo [4/4] Database already exists.
)

echo.
echo  Server running at: http://127.0.0.1:5000
echo  Press Ctrl+C to stop.
echo.

python run.py
pause
