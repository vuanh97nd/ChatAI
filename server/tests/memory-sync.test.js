import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import root,{runMemorySync as rootSync,memorySyncConfig as rootConfig} from '../../work.js';
import worker,{runMemorySync,memorySyncConfig} from '../worker.js';

function database(){
 const raw=new DatabaseSync(':memory:');
 return {raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){raw.exec('BEGIN');try{const out=[];for(const item of items)out.push(await item.run());raw.exec('COMMIT');return out;}catch(e){raw.exec('ROLLBACK');throw e;}}};
}
function environment(peer,local,remote){
 const values=new Map();
 return {DB:database(),ADMIN_KEY:'fixture-admin',MEMORY_SYNC_KEY:'fixture-replication-key-at-least32-chars',
  MEMORY_SYNC_PEER:peer,MEMORY_SYNC_ACCOUNTS:JSON.stringify([{local,remote}]),MEMORY_SYNC_SHARED:'true',
  MEMORY_ENCRYPTION_KEY:Buffer.alloc(32,7).toString('base64'),MEMORY_KV:{async get(k){return values.get(k)??null;},async put(k,v){values.set(k,v);},async delete(k){values.delete(k);}},values};
}
async function request(w,env,path,body,headers={}){
 return w.fetch(new Request('https://local.example'+path,{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(body)}),env,{});
}
const record=(id=1)=>({id:id.toString(16).padStart(64,'0'),tool:'plaxis_commands',task:'private example',arguments:'{"command":"read"}',evidence:'verified',updated:'2020-01-01T00:00:00.000Z',outcome:'success'});

for(const [name,w,sync,config] of [['root',root,rootSync,rootConfig],['server',worker,runMemorySync,memorySyncConfig]]){
 test(name+': explicit configuration and secret prevent private exports',async()=>{
  assert.equal(config({}),null);
  assert.throws(()=>config({MEMORY_SYNC_PEER:'http://peer.example',MEMORY_SYNC_KEY:'a'.repeat(40)}));
  assert.throws(()=>config({MEMORY_SYNC_PEER:'https://peer.example',MEMORY_SYNC_KEY:'a'.repeat(40),MEMORY_SYNC_ACCOUNTS:'[{"local":"admin","remote":"bob"}]'}));
  assert.equal(config({MEMORY_SYNC_PEER:'https://peer.example',MEMORY_SYNC_KEY:'a'.repeat(40),MEMORY_SYNC_ACCOUNTS:'[{"local":"admin","remote":"admin"}]'}).pairs.length,1);
  const env=environment('https://peer.example','alice','bob');
  const response=await request(w,env,'/api/internal/memory-sync/export',{owner:'alice',kind:'lessons',cursor:0});
  assert.equal(response.status,401);
  const blocked=await request(w,env,'/api/internal/memory-sync/export',{owner:'stranger',kind:'lessons',cursor:0},{Authorization:'Bearer '+env.MEMORY_SYNC_KEY});
  assert.equal(blocked.status,403);
 });
 test(name+': two-way lesson/private memory replication is idempotent and propagates deletions',async()=>{
  const a=environment('https://b.example','alice','bob'),b=environment('https://a.example','bob','alice');
  await request(w,a,'/api/lessons/list',{username:'admin',key:a.ADMIN_KEY});
  await request(w,b,'/api/lessons/list',{username:'admin',key:b.ADMIN_KEY});
  for(const [env,owner] of [[a,'alice'],[b,'bob']])env.DB.raw.prepare("INSERT INTO users(username,key,tier,expires_at) VALUES(?,'fixture-password','pro','Vĩnh viễn')").run(owner);
  const call=(env,path,body,owner)=>request(w,env,path,{...body,username:owner,key:owner==='admin'?env.ADMIN_KEY:'fixture-password'});
  assert.equal((await call(a,'/api/lessons/put',{scope:'private',records:[record()]},'alice')).status,200);
  assert.equal((await call(a,'/api/lessons/put',{scope:'shared',records:[record(2)]},'admin')).status,200);
  const id='12345678-1234-1234-1234-123456789012';
  assert.equal((await call(a,'/api/memory/personal/put',{id,title:'Design',text:'Pile depth 12 m',confirm:true},'alice')).status,200);
  const pullFrom=env=>async(url,options)=>w.fetch(new Request(url,options),env,{});
  let result=await sync(b,pullFrom(a));
  assert.equal(result.errors,0);assert.equal(result.written,3);
  assert.equal(b.DB.raw.prepare("SELECT COUNT(*) AS n FROM ai_lessons WHERE owner IN ('bob','@shared')").get().n,2);
  assert.equal(b.DB.raw.prepare("SELECT COUNT(*) AS n FROM ai_lessons WHERE owner='alice'").get().n,0);
  let personal=await (await call(b,'/api/memory/personal/list',{},'bob')).json();
  assert.equal(personal.items[0].text,'Pile depth 12 m');
  const peerRaw=[...b.values.values()][0];assert.ok(!peerRaw.includes('Pile depth'));
  assert.equal((await sync(b,pullFrom(a))).written,0);
  assert.equal((await sync(a,pullFrom(b))).written,0);
  await new Promise(r=>setTimeout(r,5));
  await call(b,'/api/memory/personal/put',{id,title:'Design',text:'Pile depth 15 m',confirm:true},'bob');
  assert.equal((await sync(a,pullFrom(b))).written,1);
  personal=await (await call(a,'/api/memory/personal/list',{},'alice')).json();assert.equal(personal.items[0].text,'Pile depth 15 m');
  assert.equal((await sync(b,pullFrom(a))).written,0);
  await new Promise(r=>setTimeout(r,5));
  await call(a,'/api/admin/lessons/withdraw',{id:record(2).id},'admin');
  await call(a,'/api/memory/personal/delete',{id,confirm:true},'alice');
  result=await sync(b,pullFrom(a));assert.equal(result.errors,0);assert.equal(result.written,2);
  assert.equal(b.DB.raw.prepare("SELECT deleted FROM ai_lessons WHERE owner='@shared'").get().deleted,1);
  personal=await (await call(b,'/api/memory/personal/list',{},'bob')).json();assert.equal(personal.items.length,0);
  assert.equal((await sync(a,pullFrom(b))).written,0);
 });
 test(name+': offline peer preserves cursor and equal-version conflict does not overwrite',async()=>{
  const a=environment('https://b.example','alice','bob'),b=environment('https://a.example','bob','alice');
  await request(w,a,'/api/lessons/list',{username:'admin',key:a.ADMIN_KEY});
  await request(w,b,'/api/lessons/list',{username:'admin',key:b.ADMIN_KEY});
  for(const [env,owner] of [[a,'alice'],[b,'bob']])env.DB.raw.prepare("INSERT INTO users(username,key,tier,expires_at) VALUES(?,'fixture-password','pro','Vĩnh viễn')").run(owner);
  await request(w,a,'/api/lessons/put',{username:'alice',key:'fixture-password',scope:'private',records:[record()]});
  await request(w,b,'/api/lessons/put',{username:'bob',key:'fixture-password',scope:'private',records:[{...record(),evidence:'different'}]});
  for(const env of [a,b])env.DB.raw.prepare("UPDATE memory_sync_clock SET changed_at='2025-01-01T00:00:00.000Z'").run();
  const result=await sync(b,async(url,options)=>w.fetch(new Request(url,options),a,{}));
  assert.equal(result.conflicts,1);
  assert.equal(JSON.parse(b.DB.raw.prepare("SELECT data FROM ai_lessons WHERE owner='bob'").get().data).evidence,'different');
  assert.equal(b.DB.raw.prepare("SELECT COUNT(*) AS n FROM memory_sync_cursor WHERE kind='lessons' AND owner='bob|alice'").get().n,0);
  const offline=await sync(b,async()=>{throw new Error('offline');});assert.ok(offline.errors>0);
 });
 test(name+': paginated lesson backlog and shared opt-out',async()=>{
  const a=environment('https://b.example','alice','bob'),b=environment('https://a.example','bob','alice');
  await request(w,a,'/api/lessons/list',{username:'admin',key:a.ADMIN_KEY});
  await request(w,b,'/api/lessons/list',{username:'admin',key:b.ADMIN_KEY});
  for(const [env,owner] of [[a,'alice'],[b,'bob']])env.DB.raw.prepare("INSERT INTO users(username,key,tier,expires_at) VALUES(?,'fixture-password','pro','Vĩnh viễn')").run(owner);
  for(let start=1;start<46;start+=10)await request(w,a,'/api/lessons/put',{username:'alice',key:'fixture-password',scope:'private',records:Array.from({length:Math.min(10,46-start)},(_,i)=>record(start+i))});
  let requests=0;
  const result=await sync(b,async(url,options)=>{requests++;return w.fetch(new Request(url,options),a,{});});
  assert.equal(result.errors,0);assert.equal(result.written,45);assert.ok(requests>=3);
  a.MEMORY_SYNC_SHARED='false';
  assert.equal((await request(w,a,'/api/internal/memory-sync/export',{owner:'@shared',kind:'lessons',cursor:0},{Authorization:'Bearer '+a.MEMORY_SYNC_KEY})).status,403);
  assert.equal((await request(w,a,'/api/admin/memory-sync/run',{username:'alice',key:'fixture-password'})).status,403);
 });
 test(name+': admin private memory requires an explicit admin-to-admin pair',async()=>{
  const a=environment('https://b.example','admin','admin'),b=environment('https://a.example','admin','admin');
  const id='12345678-1234-1234-1234-123456789099';
  const response=await request(w,a,'/api/memory/personal/put',{username:'admin',key:a.ADMIN_KEY,id,title:'Admin note',text:'Remember CAD units',confirm:true});
  assert.equal(response.status,200);
  const result=await sync(b,async(url,options)=>w.fetch(new Request(url,options),a,{}));
  assert.equal(result.errors,0);assert.equal(result.written,1);
  const list=await (await request(w,b,'/api/memory/personal/list',{username:'admin',key:b.ADMIN_KEY})).json();
  assert.equal(list.items[0].text,'Remember CAD units');
 });
}
