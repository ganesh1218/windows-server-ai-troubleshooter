// The public host deliberately has no Windows management API or origin proxy.
export function onRequest() {
 return Response.json({detail:'Windows diagnostics are available only on your private PowerShell host.'}, {status:404,headers:{'X-WSHC-Hosting':'Cloudflare Pages','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
}
