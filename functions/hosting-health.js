// Public deployment marker only. No Windows diagnostics or credentials reach Pages.
export function onRequest() {
 return Response.json({status:'ok',hosting:'Cloudflare Pages',repository:'ganesh1218/windows-server-health-check'}, {headers:{'X-WSHC-Hosting':'Cloudflare Pages','Cache-Control':'no-store'}});
}
