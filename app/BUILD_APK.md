# 📱 Building the Road Comfort APK

This guide explains how to build a downloadable APK file for Android phones.

## ⚠️ Prerequisites

Before building, you MUST install:

### 1. **Java Development Kit (JDK) 11+**
- Download: https://www.oracle.com/java/technologies/downloads/
- Install with default settings
- Verify: Open PowerShell and run `java -version`

### 2. **Android Studio**
- Download: https://developer.android.com/studio
- Install with default settings
- During installation, ensure Android SDK is installed
- Android Studio also installs required build tools

## 🏗️ Build Methods

### **Method 1: Using PowerShell (Recommended)**

Easiest method if you have everything installed.

```powershell
# Navigate to android directory
cd C:\Users\aatis\OneDrive\Documents\IOT\IOT_pro\road-comfort-system\mobile\android

# Run build script
.\build.ps1

# Wait 3-5 minutes for completion
```

**Output**: `app\build\outputs\apk\debug\app-debug.apk`

### **Method 2: Using Command Prompt Batch File**

```cmd
# Navigate to android directory
cd C:\Users\aatis\OneDrive\Documents\IOT\IOT_pro\road-comfort-system\mobile\android

# Run build
build.bat

# Wait 3-5 minutes for completion
```

**Output**: `app\build\outputs\apk\debug\app-debug.apk`

### **Method 3: Manual Gradle Command**

If scripts don't work, try directly:

```powershell
cd C:\Users\aatis\OneDrive\Documents\IOT\IOT_pro\road-comfort-system\mobile\android

# Clean build (remove old artifacts)
.\gradlew clean

# Build debug APK
.\gradlew assembleDebug
```

**Output**: `app\build\outputs\apk\debug\app-debug.apk`

### **Method 4: Using Android Studio GUI**

If all else fails:

1. Open Android Studio
2. File → Open → Select `road-comfort-system/mobile/android`
3. Wait for project to sync (2-3 minutes)
4. Build → Build Bundle(s)/APK(s) → Build APK(s)
5. APK will be in `app/build/outputs/apk/debug/`

## 🔍 Build Process Explained

When you run `./gradlew assembleDebug`, it:

1. **Downloads dependencies** (~200 MB, first time only)
   - Kotlin compiler
   - Android SDK components
   - Libraries (OkHttp, TensorFlow Lite, etc.)

2. **Compiles source code**
   - Kotlin files → Java bytecode
   - XML layouts → compiled resources

3. **Packages APK**
   - Combines bytecode + resources + manifest
   - Creates unsigned APK (~50-80 MB)

4. **Signs APK** (debug key)
   - Makes it installable on phones
   - Debug key valid for development only

**Total time**: 3-5 minutes (first run), 1-2 minutes (subsequent builds)

## 📂 Output Location

After successful build, your APK is at:

```
C:\Users\aatis\OneDrive\Documents\IOT\IOT_pro\road-comfort-system\mobile\android\
    app\build\outputs\apk\debug\app-debug.apk
```

**Size**: Typically 50-80 MB

## ✅ Verifying Successful Build

If build succeeds, you'll see:

```
BUILD SUCCESSFUL!

APK file location:
app\build\outputs\apk\debug\app-debug.apk
```

If build fails, you'll see error messages. Common issues:

### **Error: "Java not found"**
```
Solution: Install JDK and restart PowerShell
```

### **Error: "Android SDK not found"**
```
Solution: Install Android Studio (includes Android SDK)
```

### **Error: "Gradle daemon crashed"**
```
Solution: 
.\gradlew --stop
.\gradlew clean assembleDebug
```

### **Error: "Out of memory"**
```
Solution: Edit gradle.properties:
org.gradle.jvmargs=-Xmx4096m
```

## 📲 Installing the APK

Once built, you can install on phones:

### **Option 1: Using ADB (USB Connection)**

```powershell
# Connect Android phone via USB
# Enable "USB Debugging" in phone Settings

# Install APK
adb install app\build\outputs\apk\debug\app-debug.apk

# Verify
adb shell pm list packages | findstr roadcomfort
```

### **Option 2: Direct APK Download**

1. Copy the APK file from build output
2. Upload to cloud (Google Drive, Dropbox, etc.)
3. Share download link with users
4. Users download and install manually on their phones

### **Option 3: Email**

1. Attach APK to email
2. Send to test phones
3. Users download and install

## 📤 Sharing the APK

Users can install your APK by:

1. **Download APK file**
   - From email, cloud link, or your website

2. **Enable Unknown Apps** (one-time)
   - Phone Settings → Apps → Unknown apps source → Enable

3. **Install APK**
   - Open file manager → find APK file → tap to install
   - Or: `adb install app-debug.apk`

4. **Grant Permissions**
   - App will request: Location, Sensors, Network, Notifications
   - Tap "Allow" to grant

## 🚀 Next Steps

### **For Testing**
- Build debug APK
- Install on test phones
- Verify all permissions work
- Test sensor collection

### **For Production (Google Play Store)**

Need to create a **Release APK** instead:

```powershell
# Create signing key (one-time)
keytool -genkey -v -keystore release.keystore `
  -keyalg RSA -keysize 2048 -validity 10000 `
  -alias roadcomfort

# When prompted, set passwords and personal info
```

Then build release:

```powershell
.\gradlew assembleRelease
```

Then upload to Google Play Store:
1. Create Google Play Developer account ($25 one-time)
2. Upload release APK
3. Fill app details, screenshots, description
4. Submit for review (~2-4 hours)
5. Users can install from Play Store app

## 🎯 What's Next

After building APK:

1. **Test on phone** - Install and verify functionality
2. **Collect real data** - Drive around with app running
3. **Train models** - Use collected data to train ML models
4. **Deploy backend** - Set up cloud server
5. **Release to Play Store** - Production deployment

## 📞 Troubleshooting

### Build takes very long
- First build downloads ~200 MB of dependencies
- Subsequent builds are faster (~1-2 min)
- Check internet connection

### APK is very large (>100 MB)
- Normal for debug APK
- Release APK will be smaller (~50-70 MB)
- Can be further optimized

### "Could not find tools.jar"
- Ensure JDK (not JRE) is installed
- Set JAVA_HOME environment variable

### Still stuck?
- Check Java version: `java -version` (need 11+)
- Check Android SDK path: should be in `%LOCALAPPDATA%\Android\Sdk`
- Try: `.\gradlew clean --no-daemon assembleDebug`

---

**Total Time to Build**: 3-5 minutes (first time), 1-2 minutes (subsequent)

**APK Size**: 50-80 MB (debug), ~50-70 MB (release)

**Requirements**: Java 11+, Android Studio (or SDK)

**Ready?** Run: `.\build.ps1`
