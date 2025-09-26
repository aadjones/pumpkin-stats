# Windows PowerShell script for finance dashboard development
# Usage: .\run.ps1 [command]
# Commands: setup, dev, fmt, test, clean, help

param(
    [string]$Command = "help"
)

function Show-Help {
    Write-Host "Available commands:"
    Write-Host "  .\run.ps1 setup    - Create virtual environment and install dependencies"
    Write-Host "  .\run.ps1 dev      - Run Streamlit app locally"
    Write-Host "  .\run.ps1 fmt      - Auto-format with black and isort"
    Write-Host "  .\run.ps1 test     - Run pytest suite"
    Write-Host "  .\run.ps1 clean    - Delete virtual environment"
    Write-Host "  .\run.ps1 help     - Show this help"
}

function Setup {
    Write-Host "🔧 Creating virtual environment and installing dependencies..."

    if (!(Test-Path "env")) {
        python -m venv env
    }

    & .\env\Scripts\Activate.ps1
    pip install -r requirements.txt -r requirements-dev.txt

    if (!(Test-Path ".git")) {
        Write-Host "🔧 Initializing Git repo..."
        git init
        git checkout -b main 2>$null
        if ($LASTEXITCODE -ne 0) {
            git switch -c main
        }
    }

    .\env\Scripts\pre-commit.exe install
    Write-Host "✅ Setup complete!"
}

function Start-Dev {
    Write-Host "🚀 Starting Streamlit app..."

    if (!(Test-Path "env")) {
        Write-Host "❌ Virtual environment not found. Run '.\run.ps1 setup' first."
        return
    }

    & .\env\Scripts\Activate.ps1
    streamlit run app.py
}

function Format-Code {
    Write-Host "✨ Formatting code with black and isort..."

    if (!(Test-Path "env")) {
        Write-Host "❌ Virtual environment not found. Run '.\run.ps1 setup' first."
        return
    }

    & .\env\Scripts\Activate.ps1
    isort --skip=env --skip=.git .
    black --exclude "^(env|\.git)/" .
    Write-Host "✅ Formatting complete!"
}

function Run-Tests {
    Write-Host "🧪 Running tests..."

    if (!(Test-Path "env")) {
        Write-Host "❌ Virtual environment not found. Run '.\run.ps1 setup' first."
        return
    }

    & .\env\Scripts\Activate.ps1
    $env:PYTHONPATH = "."
    pytest -q
}

function Clean-Env {
    Write-Host "🧹 Removing virtual environment..."

    if (Test-Path "env") {
        Remove-Item -Recurse -Force env
        Write-Host "✅ Virtual environment removed."
    } else {
        Write-Host "ℹ️ No virtual environment found."
    }
}

switch ($Command.ToLower()) {
    "setup" { Setup }
    "dev" { Start-Dev }
    "fmt" { Format-Code }
    "test" { Run-Tests }
    "clean" { Clean-Env }
    "help" { Show-Help }
    default { Show-Help }
}