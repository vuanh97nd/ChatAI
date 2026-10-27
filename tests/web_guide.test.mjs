import {test} from 'node:test';
import assert from 'node:assert/strict';
import {productIntent,CHATAI_GUIDE} from '../work.js';
test('product questions load the ChatAI guide',()=>{
 for(const q of ['Cách dùng PLAXIS trong ChatAI','Làm sao bật điều khiển phần mềm trên máy tính?','Kết nối điện thoại với máy tính thế nào','Cài đặt bản PC như thế nào','ChatAI có những tính năng gì'])assert.equal(productIntent(q),true,q);
});
test('ordinary questions do not',()=>{
 for(const q of ['Giải thích hệ số an toàn Bishop','Viết email xin nghỉ phép','Thời tiết Hà Nội hôm nay'])assert.equal(productIntent(q),false,q);
});
test('guide covers PC control, engineering software and phone link',()=>{
 for(const k of ['Điều khiển ứng dụng','PLAXIS','GeoStudio','AutoCAD','Kết nối điện thoại','Ollama'])assert.ok(CHATAI_GUIDE.includes(k),k);
 assert.ok(CHATAI_GUIDE.length<20000);
});
