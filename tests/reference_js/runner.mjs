import { createInterface } from 'node:readline';
import { predict } from './predict.js';
const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of lines) {
  try { console.log(JSON.stringify(predict(JSON.parse(line)))); }
  catch (e) { console.log(JSON.stringify({ error: e.code ?? 'REFERENCE_ERROR' })); }
}
