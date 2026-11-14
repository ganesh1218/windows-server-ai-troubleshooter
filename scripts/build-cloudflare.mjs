// Build an independent Worker from public dist/ files only; no private report paths are read.
import {readFile,readdir,mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const assets={};
async function walk(folder){
 for(const entry of await readdir(folder,{withFileTypes:true})){
  const absolute=path.join(folder,entry.name);
  if(entry.isDirectory()){await walk(absolute);continue;}
  const relative=path.relative(path.join(root,'dist'),absolute).split(path.sep).join('/');
  const extension=path.extname(relative);
  const type={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8'}[extension];
  if(!type)throw Error('Unexpected public asset type: '+relative);
  assets['/'+relative]={body:await readFile(absolute,'utf8'),type};
 }
}
await walk(path.join(root,'dist'));
if(!assets['/index.html'])throw Error('Build dist/index.html first.');
const source=`// Generated public dashboard assets. Never contains target-server credentials or reports.
const assets=${JSON.stringify(assets)};
export default {
 async fetch(request){
  const url=new URL(request.url);
  const headers={
   'X-WSHC-Hosting':'Cloudflare Workers',
   'X-Content-Type-Options':'nosniff',
   'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
   'Referrer-Policy':'strict-origin-when-cross-origin'
  };
  if(!['GET','HEAD'].includes(request.method))return new Response('Method not allowed',{status:405,headers:{...headers,Allow:'GET, HEAD'}});
  if(url.pathname.startsWith('/api/'))return new Response('Private PowerShell APIs are not hosted here.',{status:404,headers});
  if(url.pathname==='/hosting-health')return Response.json({status:'ok',hosting:'Cloudflare Workers',repository:'ganesh1218/windows-server-health-check'},{headers:{...headers,'Cache-Control':'no-store'}});
  const key=url.pathname==='/'?'/index.html':url.pathname;
  const asset=assets[key];
  if(!asset)return new Response('Not found',{status:404,headers});
  return new Response(request.method==='HEAD'?null:asset.body,{headers:{...headers,'Content-Type':asset.type,'Cache-Control':key==='/index.html'?'no-store':'public, max-age=31536000, immutable'}});
 }
};
`;
await mkdir(path.join(root,'.cloudflare-build'),{recursive:true});
await writeFile(path.join(root,'.cloudflare-build/worker.mjs'),source);
console.log(`Built standalone Cloudflare Worker with ${Object.keys(assets).length} public assets.`);
