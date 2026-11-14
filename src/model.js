export const sortedDrives = drives => [...(drives || [])].sort((a,b) => (a.name === 'C:' ? -1 : b.name === 'C:' ? 1 : a.name.localeCompare(b.name)));
export const percentUsed = drive => drive.totalGB > 0 && drive.freeGB != null ? Math.round((1-drive.freeGB/drive.totalGB)*100) : null;
// Fixed snapshot thresholds. Missing measurements remain unknown.
export function healthChecks(s) {
  const drives = sortedDrives(s.drives);
  return [
    {name:'CPU utilization',state:s.cpu==null?'Unknown':s.cpu>=85?'Review':'Passing'},
    {name:'Physical memory',state:s.memory?.usedPercent==null?'Unknown':s.memory.usedPercent>=85?'Review':'Passing'},
    {name:'Drive capacity',state:drives.some(d=>percentUsed(d)>=85)?'Review':!drives.length||drives.some(d=>percentUsed(d)==null)?'Unknown':'Passing'},
    {name:'Remote Desktop',state:!s.rdp?'Unknown':s.rdp.enabled==null||s.rdp.serviceState==null||s.rdp.tcp3389==null?'Unknown':s.rdp.enabled&&s.rdp.serviceState==='Running'&&s.rdp.tcp3389?'Passing':'Review'},
    {name:'Collection completeness',state:s.errors?.length?'Review':'Passing'}
  ];
}
// Findings identify evidence to review; they do not establish root cause or compliance.
export function findings(s) {
  const items=[];
  if(s.cpu>=85) items.push({severity:'Warning',title:'CPU pressure',detail:`CPU utilization is ${s.cpu}%. Capture another sample and inspect the busiest processes.`});
  if(s.memory?.usedPercent>=85) items.push({severity:'Warning',title:'Memory pressure',detail:`Physical RAM is ${s.memory.usedPercent}% utilized. Verify process working sets and paging.`});
  sortedDrives(s.drives).filter(d=>percentUsed(d)>=85).forEach(d=>items.push({severity:'Critical',title:`Low space on ${d.name}`,detail:`${d.freeGB} GB free of ${d.totalGB} GB. Review growth and retention before removing files.`}));
  if(s.rdp && (!s.rdp.enabled || s.rdp.serviceState!=='Running' || !s.rdp.tcp3389)) items.push({severity:'Warning',title:'RDP needs verification',detail:'Review Remote Desktop settings, TermService, configured port and firewall from the management network.'});
  const stopped=(s.services||[]).filter(x=>x.startMode==='Auto' && x.state!=='Running');
  if(stopped.length) items.push({severity:'Warning',title:`${stopped.length} automatic service${stopped.length===1?'':'s'} stopped`,detail:stopped.map(x=>x.displayName||x.name).join(', ')+'. Trigger-start services may legitimately be stopped.'});
  const unexpected=(s.reboots||[]).filter(e=>[41,6008].includes(e.id));
  if(unexpected.length) items.push({severity:'Warning',title:'Unexpected shutdown evidence',detail:`${unexpected.length} event records; records can refer to the same incident. Event 41/6008 alone cannot identify the cause or initiating account.`});
  if(s.errors?.length) items.push({severity:'Unknown',title:'Partial collection',detail:s.errors.map(x=>x.section).join(', ')+': unavailable data must be verified.'});
  return items;
}
