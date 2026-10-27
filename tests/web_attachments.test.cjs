const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'..','web-demo','app.js'),'utf8');
const c=vm.createContext({});
vm.runInContext(source.slice(source.indexOf('function readDxfText('),source.indexOf('async function readAttachment(')),c);

const dxf=['0','SECTION','2','ENTITIES',
 '0','LINE','8','MAT_CAT','10','0','20','0','11','25.5','21','8.2',
 '0','TEXT','8','GHI_CHU','10','3','20','4','1','Đê K12+300 - MNN 1.8m',
 '0','MTEXT','8','GHI_CHU','10','5','20','6','1','Lớp 1\\PSét pha',
 '0','ENDSEC','0','EOF'].join('\n');

test('DXF reader lists entities, layers, bounds and all text',()=>{
 const out=c.readDxfText(dxf);
 assert.match(out,/LINE 1/);assert.match(out,/TEXT 1/);assert.match(out,/MTEXT 1/);
 assert.match(out,/MAT_CAT/);assert.match(out,/GHI_CHU/);
 assert.match(out,/X 0\.00 → 25\.50, Y 0\.00 → 8\.20/);
 assert.match(out,/Đê K12\+300 - MNN 1\.8m/);assert.match(out,/Lớp 1 Sét pha/);
});
test('DXF reader rejects files without entities',()=>{
 assert.throws(()=>c.readDxfText('hello'),/DXF ASCII/);
});
