Write-Host "Setting up Media Harvest Environment..." -ForegroundColor Cyan

if (!(Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

Write-Host "Installing dependencies..."
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\pip install -r requirements.txt

# Copy .env.example to .env if it doesn't exist
if (!(Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — edit it if you need Gemini API key." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "  1. .\venv\Scripts\Activate.ps1"
Write-Host "  2. python -m media_harvest --help"
Write-Host ""
Write-Host "Quick start:" -ForegroundColor Cyan
Write-Host "  python -m media_harvest init my-song-project"
Write-Host "  python -m media_harvest download --project my-song-project --url 'https://youtube.com/watch?v=...'"
Write-Host "  python -m media_harvest transcribe --project my-song-project"
