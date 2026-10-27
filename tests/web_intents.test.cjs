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
