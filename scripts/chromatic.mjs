import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';
import readline from 'node:readline';
const require = createRequire(import.meta.url);
let token = process.env.CHROMATIC_PROJECT_TOKEN;
if (process.argv.includes('--token-stdin')) {
  console.log('Ready for Chromatic token on stdin.');
  const lines = readline.createInterface({ input: process.stdin });
  token = await new Promise(resolve => lines.once('line', line => { lines.close(); resolve(line.trim()); }));
}
if (!token) {
  console.error('Add CHROMATIC_PROJECT_TOKEN to your ignored .env file, then run npm run chromatic.');
  process.exit(1);
}
const child = spawn(process.execPath, [path.join(path.dirname(require.resolve('chromatic/package.json')), 'dist/bin.cjs'), ...process.argv.slice(2).filter(arg => arg !== '--token-stdin')], {
  stdio: 'inherit', env: { ...process.env, CHROMATIC_PROJECT_TOKEN: token },
});
child.on('error', () => { console.error('Could not start Chromatic. Run npm ci first.'); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
