// Used by Cloudflare Workers Builds; credentials come only from its protected environment.
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const config=JSON.parse(await readFile(path.join(root,'cloudflare-hosting.json'),'utf8'));
const token=process.env.CLOUDFLARE_API_TOKEN;
if(!token)throw Error('Cloudflare build token is missing. Configure the Worker build API token in Cloudflare.');
const code=await readFile(path.join(root,'.cloudflare-build/worker.mjs'),'utf8');
const form=new FormData();
form.append('metadata',new Blob([JSON.stringify({main_module:'worker.mjs',compatibility_date:config.compatibility_date})],{type:'application/json'}));
form.append('worker.mjs',new Blob([code],{type:'application/javascript+module'}),'worker.mjs');
const response=await fetch(`https://api.cloudflare.com/client/v4/accounts/${config.account_id}/workers/scripts/${config.worker_name}`,{method:'PUT',headers:{Authorization:'Bearer '+token},body:form});
const result=await response.json();
if(!response.ok||!result.success)throw Error('Cloudflare deployment failed: '+JSON.stringify(result.errors||[]));
console.log('Deployed '+config.worker_name+' directly to Cloudflare Workers.');
