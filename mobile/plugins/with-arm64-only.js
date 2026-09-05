/**
 * Build for arm64 phones only.
 *
 * The engine that runs a model on the phone carries a native library for
 * every processor family, and the release file doubled to 205 MB because of
 * it. Every Android phone sold since about 2017 is arm64, and the emulator on
 * an Apple computer is arm64 as well, so the other three copies are dead
 * weight.
 *
 * Set HOMESTOCK_ALL_ARCHITECTURES=1 to build them all again, for an old
 * 32 bit phone or an x86 emulator.
 */

const { withGradleProperties } = require('@expo/config-plugins')

const KEY = 'reactNativeArchitectures'

module.exports = function withArm64Only(config) {
  return withGradleProperties(config, (mod) => {
    if (process.env.HOMESTOCK_ALL_ARCHITECTURES === '1') return mod

    mod.modResults = mod.modResults.filter(
      (entry) => !(entry.type === 'property' && entry.key === KEY),
    )
    mod.modResults.push({
      type: 'comment',
      value: 'Only arm64 phones. See plugins/with-arm64-only.js.',
    })
    mod.modResults.push({ type: 'property', key: KEY, value: 'arm64-v8a' })
    return mod
  })
}
