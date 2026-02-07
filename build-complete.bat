@echo off
setlocal enabledelayedexpansion

echo.
echo ===============================================
echo Road Comfort System - APK Builder
echo ===============================================
echo.

REM Check if Java is installed
echo [1/5] Checking Java...
java -version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Java not found!
    exit /b 1
)
java -version
echo.

REM Set paths
set GRADLE_VERSION=8.7
set GRADLE_HOME=%USERPROFILE%\.gradle\wrapper\dists\gradle-%GRADLE_VERSION%\gradle-%GRADLE_VERSION%
set GRADLE_ZIP=%TEMP%\gradle-%GRADLE_VERSION%-bin.zip
set GRADLE_BIN=%GRADLE_HOME%\bin\gradle.bat

REM Download Gradle if needed
echo [2/5] Setting up Gradle...
if not exist %GRADLE_BIN% (
    echo Gradle not found. Downloading...
    
    if not exist %GRADLE_HOME% (
        echo Downloading from: https://services.gradle.org/distributions/gradle-%GRADLE_VERSION%-bin.zip
        
        curl -L -o %GRADLE_ZIP% https://services.gradle.org/distributions/gradle-%GRADLE_VERSION%-bin.zip
        
        if errorlevel 1 (
            echo ERROR: Failed to download Gradle
            exit /b 1
        )
        
        echo Extracting Gradle...
        powershell -Command "Expand-Archive -Path '%GRADLE_ZIP%' -DestinationPath '%USERPROFILE%\.gradle\wrapper\dists\gradle-%GRADLE_VERSION%' -Force"
        
        del %GRADLE_ZIP%
        echo Gradle installed successfully!
    )
) else (
    echo Gradle found!
)

echo.

REM Show Gradle version
echo Gradle version:
call %GRADLE_BIN% --version
echo.

REM Stop any running gradle daemons
echo [3/5] Cleaning up old Gradle daemons...
call %GRADLE_BIN% --stop >nul 2>&1
echo Done.
echo.

REM Download plugins (first run downloads Android plugin)
echo [4/5] Downloading Android plugin (first run only)...
call %GRADLE_BIN% help -q >nul 2>&1
echo.

REM Build APK
echo [5/5] Building APK...
echo This may take 5-10 minutes on first run...
echo.

call %GRADLE_BIN% clean assembleDebug 

if errorlevel 1 (
    echo.
    echo ===============================================
    echo BUILD FAILED!
    echo ===============================================
    exit /b 1
)

REM Verify APK was created
echo.
echo [FINAL] Verifying APK...
if exist "app\build\outputs\apk\debug\app-debug.apk" (
    for %%A in ("app\build\outputs\apk\debug\app-debug.apk") do set "APKSIZE=%%~zA"
    
    echo.
    echo ===============================================
    echo BUILD SUCCESSFUL!
    echo ===============================================
    echo.
    echo Your APK is ready:
    echo Location: %CD%\app\build\outputs\apk\debug\app-debug.apk
    echo Size: !APKSIZE! bytes
    echo.
    echo Next steps:
    echo 1. Transfer APK to your Android phone
    echo 2. Open file manager and tap app-debug.apk
    echo 3. Click Install
    echo 4. Grant requested permissions
    echo 5. Open "Road Comfort Data Collector" app
    echo 6. Click "Start Collection"
    echo.
    pause
) else (
    echo ERROR: APK was not created!
    exit /b 1
)

endlocal
