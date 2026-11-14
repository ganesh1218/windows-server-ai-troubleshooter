import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
test('Cloudflare config uses the expected hostname and independent Worker',async()=>{
 const c=JSON.parse(await readFile(new URL('../cloudflare-hosting.json',import.meta.url),'utf8'));
 assert.equal(c.hostname,'wshc.ganesh18.dpdns.org');assert.equal(c.worker_name,'wshc');
});
test('Cloudflare generator does not proxy the old host or expose management APIs',async()=>{
 const code=await readFile(new URL('../scripts/build-cloudflare.mjs',import.meta.url),'utf8');
 assert.ok(!code.includes('chatgpt.site'));assert.ok(code.includes("url.pathname.startsWith('/api/')"));assert.ok(code.includes('Cloudflare Workers'));
});
