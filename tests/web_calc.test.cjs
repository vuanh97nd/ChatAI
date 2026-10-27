const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'..','web-demo','app.js'),'utf8');
const c=vm.createContext({});
{const a=src.indexOf('function calcRequest('),b=src.indexOf('let pyWorker');vm.runInContext(src.slice(a,b),c);}

test('calculation questions ask the AI for runnable code',()=>{
 for(const q of ['Tính lực dọc trục cọc với tải 250 kN và hệ số 1.15','Giải phương trình x^2 - 5x + 6 = 0','Lãi suất 7% một năm, gửi 100 triệu sau 3 năm được bao nhiêu?','Trung bình của 12, 15, 18 là bao nhiêu'])assert.equal(c.calcRequest(q),true,q);
});
test('questions without numbers or computation do not',()=>{
 for(const q of ['Tính cách của người Hà Nội','Viết email xin nghỉ phép','Giải thích phương pháp Bishop'])assert.equal(c.calcRequest(q),false,q);
});
test('multi-part requests get the plan-and-check instruction',()=>{
 assert.equal(c.complexRequest('Hãy:\n1. Tóm tắt báo cáo\n2. Lập bảng số liệu\n3. Đề xuất giải pháp'),true);
 assert.equal(c.complexRequest('Thủ đô Việt Nam là gì?'),false);
 assert.equal(c.complexRequest('Đê là gì? Vì sao cần gia cố?'),true);
});
