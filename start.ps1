Set-Location "C:/Users/reeva/OneDrive/Desktop/reevz-tui"

if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
	Write-Host "Missing .venv. Create it with: python -m venv .venv" -ForegroundColor Yellow
	exit 1
}

.\.venv\Scripts\Activate.ps1

python app.py

exit