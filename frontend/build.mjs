// Bundles the viewer (Mol* included) into ../exonview3d/web/static/.
import { build } from 'esbuild';

// Mol* ships an emscripten video encoder that mentions Node builtins but
// only uses them under Node. Resolve them to an empty module for browsers.
const stubNodeBuiltins = {
  name: 'stub-node-builtins',
  setup(b) {
    b.onResolve({ filter: /^(fs|path|crypto)$/ }, (args) => ({ path: args.path, namespace: 'stub' }));
    b.onLoad({ filter: /.*/, namespace: 'stub' }, () => ({ contents: 'module.exports = {};', loader: 'js' }));
  },
};

await build({
  plugins: [stubNodeBuiltins],
  entryPoints: { app: 'src/main.js' },
  bundle: true,
  minify: true,
  format: 'iife',
  target: ['es2020'],
  outdir: '../exonview3d/web/static',
  loader: {
    '.woff': 'dataurl', '.woff2': 'dataurl', '.ttf': 'dataurl',
    '.png': 'dataurl', '.svg': 'dataurl', '.jpg': 'dataurl', '.gif': 'dataurl',
  },
  define: { 'process.env.NODE_ENV': '"production"', 'global': 'window' },
  logLevel: 'info',
});
