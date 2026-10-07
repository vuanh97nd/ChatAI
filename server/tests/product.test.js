import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import worker,{reserveCloud,releaseCloud,supportAPI,validateHelpAttachment} from '../worker.js';
function database(){
 const raw=new DatabaseSync(':memory:');
 const db={raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){raw.exec('BEGIN');try{const out=[];for(const item of items)out.push(await item.run());raw.exec('COMMIT');return out;}catch(e){raw.exec('ROLLBACK');throw e;}}};return db;
}
function environment(){return {DB:database(),ADMIN_KEY:'test-admin-key-with-enough-length',AI:{async run(){return new ReadableStream({start(c){c.enqueue(new TextEncoder().encode('data: {"response":"Xin chào"}\n\ndata: [DONE]\n\n'));c.close();}});}}};}
function req(path,body){return new Request('https://example.workers.dev'+path,{method:'POST',headers:{'Content-Type':'application/json','CF-Connecting-IP':'192.0.2.1'},body:JSON.stringify(body)});}
test('daily budget is atomic with parallel requests and legacy counters stay unchanged',async()=>{
 const env=environment();env.CLOUD_DAILY_REQUEST_LIMIT=4;
 await env.DB.batch([env.DB.prepare('CREATE TABLE cloud_trials(owner TEXT PRIMARY KEY,used INTEGER CHECK(used BETWEEN 0 AND 3))')]);
 env.DB.raw.prepare('INSERT INTO cloud_trials VALUES(?,?)').run('alice',3);
 const reservations=await Promise.all(Array.from({length:6},()=>reserveCloud(env,'alice')));
 assert.equal(reservations.filter(r=>r===null).length,4);assert.equal(reservations.filter(r=>r?.status===429).length,2);
 assert.equal(env.DB.raw.prepare('SELECT used FROM cloud_trials WHERE owner=?').get('alice').used,3);
 assert.equal((await reserveCloud(env,'bob')).status,429);
 await releaseCloud(env,'alice');assert.equal((await reserveCloud(env,'alice')).status,429);
});
test('global request budget fails closed without writing legacy counters',async()=>{
 const env=environment();env.CLOUD_DAILY_REQUEST_LIMIT=1;
 assert.equal(await reserveCloud(env,'alice'),null);assert.equal((await reserveCloud(env,'bob')).status,429);
 assert.equal(env.DB.raw.prepare('SELECT COUNT(*) AS n FROM cloud_trials').get().n,0);
});
test('guest can receive more than three answers and cannot reuse identity after account linking',async()=>{
 const env=environment(),body={guest_token:'a'.repeat(64),text:'Xin chào'};
 for(let i=0;i<5;i++){
  const response=await worker.fetch(req('/api/cloud/chat',body),env,{});assert.equal(response.status,200);
  const frames=await response.text();assert.match(frames,/Xin chào/);assert.ok(!frames.includes('"switch_required":true'));
 }
 const logged=await worker.fetch(req('/api/cloud/chat',{...body,username:'admin',key:env.ADMIN_KEY}),env,{});assert.equal(logged.status,200);await logged.text();
 const anonymousAgain=await worker.fetch(req('/api/cloud/chat',body),env,{});assert.equal(anonymousAgain.status,401);
});
test('empty and partial responses retain daily reservations without touching legacy counters',async()=>{
 const env=environment();env.AI.run=async()=>new ReadableStream({start(c){c.close();}});
 const body={guest_token:'b'.repeat(64),text:'Xin chào'};
 const response=await worker.fetch(req('/api/cloud/chat',body),env,{});await response.text();
 assert.equal(env.DB.raw.prepare('SELECT used FROM cloud_daily').get().used,1);
 env.AI.run=async()=>new ReadableStream({start(c){c.enqueue(new TextEncoder().encode('data: {"response":"Một phần"}\n\ndata: {"error":"interrupted"}\n\n'));c.close();}});
 const partial=await worker.fetch(req('/api/cloud/chat',body),env,{});assert.match(await partial.text(),/event: error/);
 assert.equal(env.DB.raw.prepare('SELECT used FROM cloud_daily').get().used,2);
 assert.equal(env.DB.raw.prepare('SELECT COUNT(*) AS n FROM cloud_trials').get().n,0);
});
test('web disabled does not call search and invalid input never calls AI',async()=>{
 const env=environment();let calls=0;env.AI.run=async()=>{calls++;return new ReadableStream({start(c){c.enqueue(new TextEncoder().encode('data: {"response":"OK"}\n\n'));c.close();}});};
 const body={guest_token:'c'.repeat(64),text:'Kiến thức',web_search:false};
 const result=await worker.fetch(req('/api/cloud/chat',body),env,{});await result.text();assert.equal(result.status,200);assert.equal(calls,1);
 const bad=await worker.fetch(req('/api/cloud/chat',{...body,text:''}),env,{});assert.equal(bad.status,400);assert.equal(calls,1);
});
test('support isolates tickets; admin replies, attachment and unread are persisted',async()=>{
 const env=environment(),alice={username:'alice'},bob={username:'bob'},admin={username:'admin',role:'system'},id=crypto.randomUUID();
 const attachment={name:'demo.txt',data:btoa('demo'),mime:'text/plain'};
 assert.equal((await supportAPI(env,alice,'/api/support/create',{id,title:'Cần hỗ trợ',category:'Báo lỗi',text:'Không mở được',attachment})).status,200);
 assert.equal((await supportAPI(env,bob,'/api/support/read',{id})).status,403);
 assert.equal((await supportAPI(env,bob,'/api/support/status',{id,status:'Đã đóng'})).status,403);
 const message_id=crypto.randomUUID();
 await supportAPI(env,admin,'/api/support/reply',{id,text:'Đã kiểm tra',message_id});
 await supportAPI(env,admin,'/api/support/reply',{id,text:'Đã kiểm tra',message_id});
 assert.equal(env.DB.raw.prepare('SELECT COUNT(*) AS n FROM help_messages').get().n,2);
 env.DB.raw.exec("UPDATE help_messages SET created='2026-10-06T00:00:00.000Z'");
 const list=await (await supportAPI(env,alice,'/api/support/list',{})).json();assert.equal(list.items[0].unread,1);
 const read=await (await supportAPI(env,alice,'/api/support/read',{id})).json();assert.equal(read.messages.length,2);assert.equal(read.messages[0].attachment.name,'demo.txt');assert.equal(read.messages[0].attachment.data,undefined);
 const file=await (await supportAPI(env,alice,'/api/support/attachment',{id,message_id:id})).json();assert.equal(file.file.data,btoa('demo'));
 assert.equal((await supportAPI(env,bob,'/api/support/attachment',{id,message_id:id})).status,403);
 assert.equal((await (await supportAPI(env,alice,'/api/support/list',{})).json()).items[0].unread,0);
 assert.equal((await (await supportAPI(env,bob,'/api/support/list',{})).json()).items.length,0);
 await supportAPI(env,admin,'/api/support/reply',{id,text:'Tin tiếp theo',message_id:crypto.randomUUID()});
 env.DB.raw.exec("UPDATE help_messages SET created='2026-10-06T00:00:00.000Z'");
 assert.equal((await (await supportAPI(env,alice,'/api/support/list',{})).json()).items[0].unread,1);
});
test('support attachment paths, invalid encoding and oversized files rejected',()=>{
 assert.equal(validateHelpAttachment({name:'../secret',data:btoa('a')}),false);
 assert.equal(validateHelpAttachment({name:'x',data:'not-base64!'}),false);
 assert.equal(validateHelpAttachment({name:'x',data:'a'.repeat(1400000)}),false);
});
test('JSON and streaming Cloudflare share the daily request budget',async()=>{
 const env=environment(),original=env.AI.run;env.CLOUD_DAILY_REQUEST_LIMIT=3;
 env.AI.run=async(model,input)=>input.stream?original(model,input):{response:'Nội dung trả lời'};
 const body={username:'admin',key:env.ADMIN_KEY,text:'Xin chào',provider:'cloudflare'};
 for(let i=0;i<2;i++){const r=await worker.fetch(req('/api/chat/stream',body),env,{});assert.equal(r.status,200);await r.text();}
 const third=await worker.fetch(req('/api/chat/ai',body),env,{});assert.equal(third.status,200);assert.equal((await third.json()).source,'cloudflare');
 const fourth=await worker.fetch(req('/api/chat/ai',body),env,{});assert.equal(fourth.status,429);
 const fifth=await worker.fetch(req('/api/chat/stream',body),env,{});assert.equal(fifth.status,429);
});

test('profile is private, persists contacts, updates display name and cannot change account rights',async()=>{
 const {profileAPI}=await import('../worker.js'),env=environment();
 env.DB.raw.exec("CREATE TABLE users(username TEXT PRIMARY KEY,fullname TEXT,email TEXT,updated_at TEXT,role TEXT,key TEXT)");
 env.DB.raw.prepare('INSERT INTO users VALUES(?,?,?,?,?,?)').run('alice','Alice','','','user','alice-key');
 env.DB.raw.prepare('INSERT INTO users VALUES(?,?,?,?,?,?)').run('bob','Bob','','','user','bob-key');
 const profile={fullname:'Nguyễn Văn An',email:'an@example.com',phone:'+84 912 345 678',avatar:'data:image/jpeg;base64,'+btoa(String.fromCharCode(255,216,255,0))};
 const updated=await profileAPI(env,{username:'alice'},'/api/account/profile/update',{profile});assert.equal(updated.status,200);
 const own=await (await profileAPI(env,{username:'alice'},'/api/account/profile/get',{})).json();assert.equal(own.profile.fullname,profile.fullname);assert.equal(own.profile.avatar,profile.avatar);assert.equal(own.profile.phone,profile.phone);
 const other=await (await profileAPI(env,{username:'bob',fullname:'Bob'},'/api/account/profile/get',{target_username:'alice'})).json();assert.equal(other.profile.username,'bob');assert.equal(other.profile.avatar,'');
 const row=env.DB.raw.prepare('SELECT * FROM users WHERE username=?').get('alice');assert.equal(row.fullname,profile.fullname);assert.equal(row.role,'user');assert.equal(row.key,'alice-key');
 const tampered=await profileAPI(env,{username:'alice'},'/api/account/profile/update',{profile:{...profile,username:'bob',role:'system'}});assert.equal(tampered.status,400);
 assert.equal(env.DB.raw.prepare('SELECT fullname FROM users WHERE username=?').get('bob').fullname,'Bob');
 const removed=await profileAPI(env,{username:'alice'},'/api/account/profile/update',{profile:{fullname:'An',email:'',phone:'',avatar:''}});assert.equal(removed.status,200);
 assert.equal((await (await profileAPI(env,{username:'alice'},'/api/account/profile/get',{})).json()).profile.avatar,'');
});
test('profile routes require authentication and validators reject executable or oversized avatars',async()=>{
 const {validateProfile}=await import('../worker.js');const env=environment();
 const unauth=await worker.fetch(req('/api/account/profile/get',{username:'unknown',key:'wrong'}),env,{});assert.equal(unauth.status,401);
 assert.equal(validateProfile({fullname:'An',email:'invalid'}),null);
 assert.equal(validateProfile({fullname:'An',phone:'12'}),null);
 assert.equal(validateProfile({fullname:'An',avatar:'data:image/svg+xml;base64,'+btoa('<svg/>')}),null);
 assert.equal(validateProfile({fullname:'An',avatar:'data:image/jpeg;base64,'+'a'.repeat(180000)}),null);
 assert.equal(validateProfile({fullname:'An',password:'new-password'}),null);
});
