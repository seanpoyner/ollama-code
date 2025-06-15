# PowerShell installation script for ollama-code on Windows

Write-Host "===================================="
Write-Host " Ollama Code Windows Installer" -ForegroundColor Cyan
Write-Host "===================================="
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>$null
    Write-Host "✓ Python is installed: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python from https://python.org"
    pause
    exit 1
}

# Function to install packages
function Install-Package {
    param(
        [string]$PackageName,
        [string]$DisplayName = $PackageName
    )
    
    Write-Host "Installing $DisplayName..." -NoNewline
    
    $output = pip install $PackageName 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✓" -ForegroundColor Green
        return $true
    } else {
        Write-Host " ✗" -ForegroundColor Red
        return $false
    }
}

Write-Host ""
Write-Host "Installing required dependencies..." -ForegroundColor Yellow
Write-Host ""

# Install dependencies one by one
$packages = @(
    @{Name="ollama"; Display="Ollama Python client"},
    @{Name="rich"; Display="Rich (terminal formatting)"},
    @{Name="requests"; Display="Requests"},
    @{Name="pyyaml"; Display="PyYAML"},
    @{Name="chromadb"; Display="ChromaDB (vector database)"}
)

$allSuccess = $true

foreach ($pkg in $packages) {
    $success = Install-Package -PackageName $pkg.Name -DisplayName $pkg.Display
    if (-not $success) {
        $allSuccess = $false
    }
}

Write-Host ""

if (-not $allSuccess) {
    Write-Host "===================================="
    Write-Host " Installation Failed" -ForegroundColor Red
    Write-Host "===================================="
    Write-Host ""
    Write-Host "Some packages failed to install."
    Write-Host ""
    Write-Host "Try creating a virtual environment:"
    Write-Host "  1. python -m venv venv" -ForegroundColor Yellow
    Write-Host "  2. .\venv\Scripts\Activate" -ForegroundColor Yellow
    Write-Host "  3. .\install_windows.ps1" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Or install with --user flag:"
    Write-Host "  pip install --user ollama rich requests pyyaml chromadb" -ForegroundColor Yellow
} else {
    Write-Host "===================================="
    Write-Host " Installation Complete!" -ForegroundColor Green
    Write-Host "===================================="
    Write-Host ""
    Write-Host "To run ollama-code:"
    Write-Host "  python ollama-code.py" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Make sure Ollama is running:"
    Write-Host "  ollama serve" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "For vector search, pull the embedding model:"
    Write-Host "  ollama pull nomic-embed-text" -ForegroundColor Yellow
}

Write-Host ""
pause