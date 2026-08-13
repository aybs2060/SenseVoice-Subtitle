$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $scriptPath
$exePath = Join-Path $scriptPath "dist\SenseVoiceSubtitle\SenseVoiceSubtitle.exe"

if (Test-Path $exePath) {
    Start-Process -FilePath $exePath
    Write-Host "SenseVoice Subtitle Window started successfully in background!" -ForegroundColor Green
} else {
    Write-Host "SenseVoiceSubtitle.exe not found!" -ForegroundColor Red
}
