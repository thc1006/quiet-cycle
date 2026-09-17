// The installed Python library is the runtime. No npm package or shell is needed.
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
const input = readFileSync(new URL('./request.json', import.meta.url), 'utf8');
const child = spawnSync(process.env.PYTHON ?? 'python', ['-m', 'quietcycle', 'predict', '-'], {
  input, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024, shell: false,
});
if (child.error) throw child.error;
if (child.status !== 0) {
  process.stderr.write(child.stderr);
  process.exit(child.status ?? 1);
}
const result = JSON.parse(child.stdout);
if (result.schema_version !== '2.0') throw new Error('Unsupported result contract');
process.stdout.write(JSON.stringify(result) + '\n');
