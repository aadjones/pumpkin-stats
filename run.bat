@echo off
REM Windows batch script for finance dashboard development
REM Usage: run.bat [command]

if "%1"=="" goto help
if "%1"=="setup" goto setup
if "%1"=="dev" goto dev
if "%1"=="fmt" goto fmt
if "%1"=="test" goto test
if "%1"=="clean" goto clean
if "%1"=="help" goto help
goto help

:setup
echo Creating virtual environment and installing dependencies...
if not exist env (
    python -m venv env
)
call env\Scripts\activate.bat
pip install -r requirements.txt -r requirements-dev.txt

if not exist .git (
    echo Initializing Git repo...
    git init
    git checkout -b main 2>nul || git switch -c main
)

env\Scripts\pre-commit.exe install
echo Setup complete!
goto end

:dev
echo Starting Streamlit app...
if not exist env (
    echo Virtual environment not found. Run 'run.bat setup' first.
    goto end
)
call env\Scripts\activate.bat
streamlit run app.py
goto end

:fmt
echo Formatting code with black and isort...
if not exist env (
    echo Virtual environment not found. Run 'run.bat setup' first.
    goto end
)
call env\Scripts\activate.bat
isort --skip=env --skip=.git .
black --exclude "(env|\.git)" .
echo Formatting complete!
goto end

:test
echo Running tests...
if not exist env (
    echo Virtual environment not found. Run 'run.bat setup' first.
    goto end
)
call env\Scripts\activate.bat
set PYTHONPATH=.
pytest -q
goto end

:clean
echo Removing virtual environment...
if exist env (
    rmdir /s /q env
    echo Virtual environment removed.
) else (
    echo No virtual environment found.
)
goto end

:help
echo Available commands:
echo   run.bat setup    - Create virtual environment and install dependencies
echo   run.bat dev      - Run Streamlit app locally
echo   run.bat fmt      - Auto-format with black and isort
echo   run.bat test     - Run pytest suite
echo   run.bat clean    - Delete virtual environment
echo   run.bat help     - Show this help
goto end

:end