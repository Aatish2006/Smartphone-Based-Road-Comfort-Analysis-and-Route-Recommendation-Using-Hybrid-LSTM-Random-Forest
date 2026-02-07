# Find Java installation
Write-Host "Searching for Java 21..." -ForegroundColor Yellow
Write-Host ""

# Common Java locations
$searchPaths = @(
    "C:\Program Files\Java",
    "C:\Program Files (x86)\Java",
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Java"
)

$javaExe = $null

foreach ($path in $searchPaths) {
    if (Test-Path $path) {
        Get-ChildItem $path -Recurse -Filter "java.exe" -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host "Found: $($_.FullName)" -ForegroundColor Green
            
            # Check version
            $versionOutput = & $_.FullName -version 2>&1
            Write-Host "Version: $($versionOutput[0])" -ForegroundColor Cyan
            
            if ($versionOutput[0] -match "21") {
                $javaExe = $_.FullName
                Write-Host "This is Java 21!" -ForegroundColor Green
            }
            Write-Host ""
        }
    }
}

if ($javaExe) {
    Write-Host "FOUND: $javaExe" -ForegroundColor Green
    Write-Host ""
    Write-Host "To add to PATH permanently, run in Admin PowerShell:" -ForegroundColor Yellow
    $javaDir = Split-Path $javaExe
    $cmd = "[Environment]::SetEnvironmentVariable('PATH', '$javaDir;' + [Environment]::GetEnvironmentVariable('PATH', 'User'), 'User')"
    Write-Host $cmd -ForegroundColor Cyan
} else {
    Write-Host "Java 21 not found in common locations." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install from: https://www.oracle.com/java/technologies/downloads/" -ForegroundColor Yellow
    Write-Host "Then restart PowerShell and try again." -ForegroundColor Yellow
}
