# PowerShell installer for ollama-code

Write-Host "Installing ollama-code dependencies..." -ForegroundColor Cyan
Write-Host ""

# Just run pip install for all packages
pip install ollama rich requests pyyaml chromadb

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Installation complete!" -ForegroundColor Green
    Write-Host "Run: python ollama-code.py" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "Installation failed!" -ForegroundColor Red
    Write-Host "Try: pip install --user ollama rich requests pyyaml chromadb" -ForegroundColor Yellow
}

Write-Host ""
pause