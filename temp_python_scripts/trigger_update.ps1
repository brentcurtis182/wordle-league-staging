# Trigger daily reset on Railway (updates both League 6 and BellyUp)
# This regenerates HTML and publishes to GitHub Pages

Write-Host "Triggering daily reset on Railway..." -ForegroundColor Cyan

$response = Invoke-WebRequest -Uri "https://wordle-league-production.up.railway.app/daily-reset" -Method POST

if ($response.StatusCode -eq 200) {
    Write-Host "SUCCESS! Both leagues updated and published." -ForegroundColor Green
    Write-Host ""
    Write-Host "Check the websites:" -ForegroundColor Yellow
    Write-Host "  League 6: https://brentcurtis182.github.io/wordle-league/league6/index.html"
    Write-Host "  BellyUp:  https://brentcurtis182.github.io/wordle-league/bellyup/index.html"
} else {
    Write-Host "FAILED! Status: $($response.StatusCode)" -ForegroundColor Red
}
