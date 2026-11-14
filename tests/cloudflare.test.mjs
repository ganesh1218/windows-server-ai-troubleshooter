import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {onRequest as health} from '../functions/hosting-health.js';
import {onRequest as api} from '../functions/api/[[path]].js';
test('Cloudflare config uses the expected hostname and Git-connected Pages project',async()=>{
 const c=JSON.parse(await readFile(new URL('../cloudflare-hosting.json',import.meta.url),'utf8'));
 assert.equal(c.hostname,'wshc.ganesh18.dpdns.org');assert.equal(c.project_name,'wshc-health-check');assert.equal(c.production_branch,'main');
});
test('Cloudflare health response identifies independent hosting',async()=>{
 const response=health();assert.equal((await response.json()).hosting,'Cloudflare Pages');assert.equal(response.headers.get('Cache-Control'),'no-store');
});
test('public Cloudflare API rejects diagnostics rather than forwarding credentials',async()=>{
 const response=api();assert.equal(response.status,404);assert.match((await response.json()).detail,/private PowerShell host/);
});
