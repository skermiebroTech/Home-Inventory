/**
 * Sign the Android release build with a key of your own.
 *
 * `expo prebuild` writes the android directory from scratch, and the template
 * signs a release build with the debug key. A debug key is not a key: anybody
 * has it, and Android refuses an update that a different key signed. This
 * plugin adds a release signing configuration that reads four Gradle
 * properties:
 *
 *   HOMESTOCK_STORE_FILE      the path of the keystore
 *   HOMESTOCK_STORE_PASSWORD  the password of the keystore
 *   HOMESTOCK_KEY_ALIAS       the name of the key inside it
 *   HOMESTOCK_KEY_PASSWORD    the password of that key
 *
 * Put them in ~/.gradle/gradle.properties, which stays outside this
 * repository. Without them the build falls back to the debug key, so a fresh
 * clone still builds.
 */

const { withAppBuildGradle } = require('@expo/config-plugins')

const CONFIG = `
        homestockRelease {
            storeFile file(findProperty('HOMESTOCK_STORE_FILE') ?: 'debug.keystore')
            storePassword findProperty('HOMESTOCK_STORE_PASSWORD') ?: 'android'
            keyAlias findProperty('HOMESTOCK_KEY_ALIAS') ?: 'androiddebugkey'
            keyPassword findProperty('HOMESTOCK_KEY_PASSWORD') ?: 'android'
        }`

module.exports = function withReleaseSigning(config) {
  return withAppBuildGradle(config, (mod) => {
    let gradle = mod.modResults.contents
    if (gradle.includes('homestockRelease')) return mod

    gradle = gradle.replace('    signingConfigs {', `    signingConfigs {${CONFIG}`)
    gradle = gradle.replace(
      /release \{\n(\s*)\/\/ Caution![\s\S]*?signingConfig signingConfigs\.debug/,
      (match, indent) =>
        `release {\n${indent}signingConfig signingConfigs.homestockRelease`,
    )

    mod.modResults.contents = gradle
    return mod
  })
}
