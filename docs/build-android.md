# Build the Android application

The result is one APK that you install on the phone with a cable. The phone
then holds the whole application, and it no longer needs Expo Go or the Metro
server on your computer.

## What the computer needs

- Node 20 and the packages: `cd mobile && npm install`
- JDK 21. On this Mac: `/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home`
- The Android SDK, in `~/Library/Android/sdk`

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
export ANDROID_HOME=$HOME/Library/Android/sdk
export ANDROID_SDK_ROOT=$ANDROID_HOME
```

## The signing key

Android refuses an update that a different key signed, so the key must live
longer than the build. Make it one time and keep it:

```bash
mkdir -p ~/.homestock
keytool -genkeypair -v -storetype PKCS12 \
  -keystore ~/.homestock/homestock-release.jks -alias homestock \
  -keyalg RSA -keysize 2048 -validity 10000
```

Then tell Gradle where it is. This file sits outside the repository, so the
password never reaches git:

```bash
cat >> ~/.gradle/gradle.properties <<'EOF'
HOMESTOCK_STORE_FILE=/Users/YOU/.homestock/homestock-release.jks
HOMESTOCK_STORE_PASSWORD=...
HOMESTOCK_KEY_ALIAS=homestock
HOMESTOCK_KEY_PASSWORD=...
EOF
```

[mobile/plugins/with-release-signing.js](../mobile/plugins/with-release-signing.js)
reads those four properties. Without them the build falls back to the debug
key, so a fresh clone still builds.

**Back the keystore up.** A lost key means the next version cannot install
over this one: the phone must remove the application first, and it loses the
queued changes that never reached the server.

## Build it

```bash
cd mobile
npx expo prebuild --platform android      # writes the android directory
cd android
./gradlew assembleRelease
```

The first build downloads the Android NDK and takes several minutes. Later
builds take about one minute.

The file appears at
`mobile/android/app/build/outputs/apk/release/app-release.apk`.

## Install it

```bash
adb devices                                # the phone must say "device"
adb install -r mobile/android/app/build/outputs/apk/release/app-release.apk
```

`-r` keeps the data of the older version. A phone that refuses the install
usually holds a copy signed by a different key: remove that copy first.

## After the install

The sign-in screen asks for the server address. Give it the address of your
server, such as `http://192.168.1.20:7850`.

The application talks to the server over plain HTTP on your own network.
Android blocks plain HTTP from Android 9, so
[mobile/app.json](../mobile/app.json) turns `usesCleartextTraffic` on through
`expo-build-properties`. Remove that setting on the day the server answers on
HTTPS.

## A new version

Raise `expo.version` and `expo.android.versionCode` in
[mobile/app.json](../mobile/app.json), then build and install again. Android
refuses to install a lower version code over a higher one.
