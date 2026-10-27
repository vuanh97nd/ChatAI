const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'..','web-demo','app.js'),'utf8');
const c=vm.createContext({});
const cut=(a,b)=>src.slice(src.indexOf(a),src.indexOf(b,src.indexOf(a)));
vm.runInContext('function selectedTool(){return "";}\n'+cut('function mediaMode(','function syncMediaOptions('),c);
vm.runInContext(cut('function chartRequest(','const CHART_COLORS'),c);
test('image requests go to the image generator whatever the AI',()=>{
 for(const q of ['Tạo ảnh con mèo','vẽ con mèo đang ngủ','Cho tôi một bức tranh phố cổ Hội An','thiết kế logo cho quán cà phê','Vẽ phong cảnh Hạ Long'])assert.equal(c.mediaMode(q),'image',q);
 assert.equal(c.mediaMode('Tạo video 8 giây cảnh biển'),'video');
});
test('charts, files and normal questions are not images',()=>{
 for(const q of ['Vẽ biểu đồ doanh thu 3 tháng','Tạo file Excel bảng lương','Giải thích hệ số an toàn','Vẽ bản vẽ DXF mặt cắt đê'])assert.equal(c.mediaMode(q),null,q);
});
test('chart block is parsed and hidden',()=>{
 assert.equal(c.chartRequest('vẽ biểu đồ cột'),true);
 const r=c.extractChartSpec('Doanh thu tăng.\n```chatai-chart\n{"chart":"bar","title":"Doanh thu","labels":["T1","T2"],"series":[{"name":"2026","values":[10,12]}]}\n```');
 assert.equal(r.clean,'Doanh thu tăng.');assert.equal(r.spec.series[0].values[1],12);
 assert.equal(c.extractChartSpec('```chatai-chart\n{"labels":1}\n```').spec.error,true);
});

vm.runInContext('function selectedTool(){return "";}\n'+cut('function fileRequest(','function FILE_INSTRUCTION('),c);
{const start=src.indexOf('function mdTables('),md=src.indexOf('function markdownToSpec(',start),end=src.indexOf('\n}\n',md)+3;vm.runInContext(src.slice(start,end),c);}
const J=v=>JSON.stringify(v);
test('file requests are recognised in natural wording',()=>{
 assert.equal(c.fileRequest('Soạn hợp đồng thuê nhà dạng Word'),'docx');
 assert.equal(c.fileRequest('cho tôi bảng lương bằng excel'),'xlsx');
 assert.equal(c.fileRequest('Làm slide thuyết trình về đê điều'),'pptx');
 assert.equal(c.fileRequest('xuất ra pdf giúp mình'),'pdf');
 assert.equal(c.fileRequest('Giải thích phương pháp Bishop'),null);
});
test('markdown answer becomes a file when the AI forgets the block',()=>{
 const md='# Báo cáo địa chất\n## Lớp đất\nMô tả chung.\n- Sét pha\n- Cát\n\n| Lớp | c |\n|---|---|\n| Sét | 18 |\n| Cát | 0 |\n## Kết luận\nĐạt yêu cầu.';
 const x=c.markdownToSpec('xlsx',md);assert.equal(J(x.sheets[0].rows),J([['Lớp','c'],['Sét',18],['Cát',0]]));
 const d=c.markdownToSpec('docx',md);assert.equal(d.title,'Báo cáo địa chất');assert.equal(d.sections[0].heading,'Lớp đất');assert.equal(J(d.sections[0].bullets),J(['Sét pha','Cát']));
 const p=c.markdownToSpec('pptx',md);assert.equal(p.slides.length,2);assert.equal(p.slides[1].title,'Kết luận');
});
