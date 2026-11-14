// Build a deterministic ZIP from an explicit list of public source files only.
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=new URL('../',import.meta.url);
const files=[
 ['connector.py','connector/connector.py'],
 ['SETUP.md','connector/SETUP.md'],
 ['scripts/Invoke-HealthCheck.ps1','scripts/Invoke-HealthCheck.ps1'],
 ['scripts/Collect-Diagnostics.ps1','scripts/Collect-Diagnostics.ps1'],
 ['scripts/Test-ConnectorEnvironment.ps1','scripts/Test-ConnectorEnvironment.ps1'],
 ['LICENSE','LICENSE'],
];
function crc32(bytes){let crc=0xffffffff;for(const byte of bytes){crc^=byte;for(let i=0;i<8;i++)crc=(crc>>>1)^((crc&1)?0xedb88320:0)}return (crc^0xffffffff)>>>0}
const local=[],central=[];let offset=0;
for(const [name,path] of files){
 const body=await readFile(new URL(path,root)),filename=Buffer.from(name),crc=crc32(body);
 const header=Buffer.alloc(30);header.writeUInt32LE(0x04034b50,0);header.writeUInt16LE(20,4);
 header.writeUInt16LE(33,12);header.writeUInt32LE(crc,14);header.writeUInt32LE(body.length,18);
 header.writeUInt32LE(body.length,22);header.writeUInt16LE(filename.length,26);
 local.push(header,filename,body);
 const entry=Buffer.alloc(46);entry.writeUInt32LE(0x02014b50,0);entry.writeUInt16LE(20,4);entry.writeUInt16LE(20,6);
 entry.writeUInt16LE(33,14);entry.writeUInt32LE(crc,16);entry.writeUInt32LE(body.length,20);
 entry.writeUInt32LE(body.length,24);entry.writeUInt16LE(filename.length,28);entry.writeUInt32LE(offset,42);
 central.push(entry,filename);offset+=header.length+filename.length+body.length;
}
const directory=Buffer.concat(central),end=Buffer.alloc(22);end.writeUInt32LE(0x06054b50,0);
end.writeUInt16LE(files.length,8);end.writeUInt16LE(files.length,10);end.writeUInt32LE(directory.length,12);end.writeUInt32LE(offset,16);
const archive=Buffer.concat([...local,directory,end]),name='windows-server-health-check-connector.zip';
await mkdir(new URL('public/downloads/',root),{recursive:true});
await writeFile(new URL('public/downloads/'+name,root),archive);
await writeFile(new URL('public/downloads/'+name+'.sha256',root),createHash('sha256').update(archive).digest('hex')+'  '+name+'\n');
console.log('Packaged Python connector (explicit source allowlist, no private data).');
