# Quick Android SDK Setup

Since the automated download failed, here's the fastest manual setup (2 minutes):

## Option 1: Install Android Studio (Easiest)

Even though latest Android Studio doesn't work, you can install an **old lightweight version** that includes the SDK:

1. Go: https://developer.android.com/studio/archive
2. Download: **Android Studio Electric Eel 2022.1.1** (small & lightweight)
3. Install normally
4. When it asks to install SDK → Click "Yes" 
5. Wait ~5 minutes for SDK to download
6. Then try building:
   ```cmd
   build-with-sdk.bat
   ```

## Option 2: Download SDK Command-Line Tools (Advanced)

If you want command-line only (no Android Studio GUI):

1. Go: https://developer.android.com/studio
2. Scroll to "Command line tools only"
3. Download the **Windows** version
4. Extract to: `C:\Users\aatis\.android\sdk\cmdline-tools\latest\`
5. Run:
   ```cmd
   build-with-sdk.bat
   ```

## Option 3: Use Pre-Built APK (Fastest)

Tell me if you'd like me to create a pre-compiled APK you can download directly (no build needed).

---

**Recommendation:** Go with **Option 1** (Android Studio Electric Eel) - it's the most reliable and takes only 5 minutes!

Once you have the SDK installed, run:
```cmd
cd C:\Users\aatis\OneDrive\Documents\IOT\IOT_pro\road-comfort-system\mobile\android
build-with-sdk.bat
```
