import deckyPlugin from "@decky/rollup";

// Decky's own toolchain: emits an ES module with a default export, which is
// what the loader imports. The IIFE config copied from GameVault produced a
// legacy-format bundle, and the loader failed with
// "TypeError: plugin_exports.default is not a function".
export default deckyPlugin({});
