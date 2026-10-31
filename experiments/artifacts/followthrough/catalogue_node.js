// One bounded buffer or independently parsed JSON objects; no framework cache.
const fs=require('fs'),crypto=require('crypto'),{isUtf8}=require('buffer');
const [file,mode,iterations,pin]=process.argv.slice(2);
const PYC=Buffer.from('.pyc'),DJANGO=Buffer.from('django/');
const start=process.hrtime.bigint();let first;const times=[];
for(let trial=0;trial<Number(iterations);trial++) {
  const t0=process.hrtime.bigint();const data=fs.readFileSync(file);
  if(crypto.createHash('sha256').update(data).digest('hex')!==pin)throw Error('integrity');
  const out=[0,0,0,0,0,0];
  if(mode==='json') {
    const rows=JSON.parse(data);
    for(const row of rows) {
      if(typeof row.name!=='string'||!row.name.length||!Number.isSafeInteger(row.size)||row.size<0||row.size>64*1024*1024||!Number.isSafeInteger(row.offset)||row.offset<0||row.offset>64*1024*1024-row.size||typeof row.sha256!=='string'||!/^[0-9a-f]{64}$/.test(row.sha256)||!isUtf8(Buffer.from(row.name)))throw Error('row schema');
      out[0]++;out[1]+=row.size;
      if(row.name.endsWith('.pyc')){out[2]++;out[3]+=row.size;}
      if(row.name.startsWith('django/')){out[4]++;out[5]+=row.size;}
    }
  } else {
    if(data.length<24||data.length>16*1024*1024||data.toString('ascii',0,8)!=='GACAT001'||data.readUInt32LE(8)!==1||data.readUInt32LE(20)!==56)throw Error('header');
    const count=data.readUInt32LE(12),bytes=data.readUInt32LE(16),pool=24+count*56;
    if(count>100000||pool+bytes!==data.length)throw Error('geometry');
    for(let i=0;i<count;i++) {
      const at=24+i*56,size=Number(data.readBigUInt64LE(at+8)),offset=data.readUInt32LE(at+16),n=data.readUInt32LE(at+20);
      if(!n||offset+n>bytes||size>64*1024*1024||Number(data.readBigUInt64LE(at))>64*1024*1024-size||!isUtf8(data.subarray(pool+offset,pool+offset+n)))throw Error('row bounds');
      // Names stay byte views; avoid constructing a JS string for the query.
      const begin=pool+offset,end=begin+n;
      out[0]++;out[1]+=size;
      if(n>=4&&data.compare(PYC,0,4,end-4,end)===0){out[2]++;out[3]+=size;}
      if(n>=7&&data.compare(DJANGO,0,7,begin,begin+7)===0){out[4]++;out[5]+=size;}
    }
  }
  times.push(Number(process.hrtime.bigint()-t0)/1e6);
  if(!first)first=out;else if(JSON.stringify(first)!==JSON.stringify(out))throw Error('changed');
}
console.log(JSON.stringify({mode,result:first,operation_ms:times,total_ms:Number(process.hrtime.bigint()-start)/1e6}));
