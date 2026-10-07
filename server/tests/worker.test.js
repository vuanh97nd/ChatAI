import {test} from 'node:test';
import assert from 'node:assert/strict';
import worker,{extractionContract} from '../worker.js';
function database(){
 return {prepare(sql){return {bind(){return this;},async run(){return {meta:{changes:1}};},async all(){return {results:[]};},async first(){return sql.includes('RETURNING used')?{used:1}:sql.includes('SELECT hits')?{hits:1}:null;}};},async batch(){return [];}};
}
function env(){return {DB:database(),ADMIN_KEY:'test-only-admin-secret-32-characters',ALLOWED_ORIGINS:'https://chat.example.com'};}
function req(path,body,headers={}){return new Request('https://worker.example.com'+path,{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(body)});}
test('health works without DB and does not expose secrets',async()=>{
 const r=await worker.fetch(new Request('https://worker.example.com/api/health'),{},{});
 assert.equal(r.status,200);assert.equal((await r.json()).app,'Chat AI');
});
test('unapproved browser origin blocked before database access',async()=>{
 const r=await worker.fetch(req('/api/login',{}, {Origin:'https://evil.example'}),env(),{});
 assert.equal(r.status,403);assert.equal(r.headers.get('Access-Control-Allow-Origin'),null);
});
test('invalid JSON rejected instead of treated as empty object',async()=>{
 const r=await worker.fetch(new Request('https://worker.example.com/api/login',{method:'POST',body:'{'}),env(),{});
 assert.equal(r.status,400);
});
test('unauthenticated logout cannot evict another device',async()=>{
 const r=await worker.fetch(req('/api/logout',{username:'victim'}),env(),{});
 assert.equal(r.status,401);
});
test('conversation API requires account authentication',async()=>{
 const r=await worker.fetch(req('/api/conversations/list',{username:'victim',key:'wrong'}),env(),{});
 assert.equal(r.status,401);
});
test('stream normalizes frames split across network chunks',async()=>{
 const e=env();e.AI={async run(){return new ReadableStream({start(c){const enc=new TextEncoder();c.enqueue(enc.encode('data: {"res'));c.enqueue(enc.encode('ponse":"Xin chào"}\n\ndata: [DONE]\n\n'));c.close();}});}};
 const r=await worker.fetch(req('/api/chat/stream',{username:'admin',key:e.ADMIN_KEY,text:'Chào bạn'}),e,{});
 assert.equal(r.status,200);const text=await r.text();assert.match(text,/event: delta/);assert.match(text,/Xin chào/);assert.match(text,/event: done/);
 assert.ok(!text.includes(e.ADMIN_KEY));
});
test('stream refuses tool requests before calling AI',async()=>{
 const e=env();e.AI={run(){throw new Error('Must not run');}};
 const r=await worker.fetch(req('/api/chat/stream',{username:'admin',key:e.ADMIN_KEY,text:'sửa file',tools:true}),e,{});
 assert.equal(r.status,400);
});
test('generic document extraction preserves explicit missing fields',()=>{
 const contract=extractionContract('document');assert.equal(contract.key,'records');assert.ok(contract.schema.properties.records.items.required.includes('missing'));
});
test('signup accepts the three required fields without email',async()=>{
 const r=await worker.fetch(req('/api/register',{fullname:'Nguyễn Văn An',username:'nguyenvanan',password:'test-password-123'}),env(),{});
 assert.equal(r.status,201);assert.equal((await r.json()).success,true);
});
test('signup rejects missing full name',async()=>{
 const r=await worker.fetch(req('/api/register',{username:'nguyenvanan',password:'test-password-123'}),env(),{});
 assert.equal(r.status,400);
});
function memoryEnvironment(){
 const index=new Map(),values=new Map();
 const db={prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){
  if(sql.startsWith('INSERT INTO personal_memory_index')){const [owner,id,key,updated]=this.args;index.set(owner+'|'+id,{owner,id,kv_key:key,updated_at:updated,deleted_at:null});}
  if(sql.startsWith('UPDATE personal_memory_index SET deleted_at')){const [deleted,owner,id]=this.args;const item=index.get(owner+'|'+id);if(item)item.deleted_at=deleted;}
  return {meta:{changes:1}};
 },async all(){return {results:sql.includes('FROM personal_memory_index')?[...index.values()].filter(i=>i.owner===this.args[0]&&!i.deleted_at):[]};},async first(){
  if(sql.includes('SELECT hits'))return {hits:1};
  if(sql.includes('FROM users'))return ['alice','bob'].includes(this.args[0])?{username:this.args[0],key:'test-memory-password',password_hash:'',salt:'',tier:'pro',expires_at:'Vĩnh viễn'}:null;
  if(sql.includes('COUNT(*) AS total FROM personal_memory_index'))return {total:[...index.values()].filter(i=>i.owner===this.args[0]&&!i.deleted_at).length};
  if(sql.includes('SELECT kv_key FROM personal_memory_index')){const item=index.get(this.args[0]+'|'+this.args[1]);return item&&!item.deleted_at?item:null;}
  return null;
 }};},async batch(){return [];}};
 const e={...env(),DB:db,MEMORY_ENCRYPTION_KEY:btoa('01234567890123456789012345678901'),MEMORY_KV:{async put(k,v){values.set(k,v);},async get(k){return values.get(k)||null;},async delete(k){values.delete(k);}}};
 return {e,index,values};
}
test('personal memories encrypted in KV and isolated per account',async()=>{
 const {e,values}=memoryEnvironment();
 const save=await worker.fetch(req('/api/memory/personal/put',{username:'alice',key:'test-memory-password',title:'Sở thích',text:'Tôi thích trả lời ngắn gọn',confirm:true}),e,{});
 assert.equal(save.status,200);const item=(await save.json()).item;
 assert.equal(values.size,1);assert.ok(![...values.values()][0].includes('Tôi thích'));
 const bob=await worker.fetch(req('/api/memory/personal/list',{username:'bob',key:'test-memory-password'}),e,{});
 assert.deepEqual((await bob.json()).items,[]);
 const alice=await worker.fetch(req('/api/memory/personal/list',{username:'alice',key:'test-memory-password'}),e,{});
 assert.equal((await alice.json()).items[0].text,'Tôi thích trả lời ngắn gọn');
 const removeOther=await worker.fetch(req('/api/memory/personal/delete',{username:'bob',key:'test-memory-password',id:item.id,confirm:true}),e,{});
 assert.equal(removeOther.status,404);
 const remove=await worker.fetch(req('/api/memory/personal/delete',{username:'alice',key:'test-memory-password',id:item.id,confirm:true}),e,{});
 assert.equal(remove.status,200);assert.equal(values.size,0);
});
test('memory write requires explicit confirmation',async()=>{
 const {e,values}=memoryEnvironment();
 const r=await worker.fetch(req('/api/memory/personal/put',{username:'alice',key:'test-memory-password',title:'x',text:'y'}),e,{});
 assert.equal(r.status,400);assert.equal(values.size,0);
});
