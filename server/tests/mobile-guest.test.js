import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import * as root from '../../work.js';
import * as server from '../worker.js';
function database(){const raw=new DatabaseSync(':memory:');return {raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return raw.prepare(sql).run(...this.args);},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){return Promise.all(items.map(item=>item.run()));}};}
for(const [name,mod] of [['root',root],['server',server]]){
 test(`${name}: public status initializes its rate table on a fresh database`,async()=>{
  const env={DB:database(),ADMIN_KEY:'test-only-secret'};
  try{
   const request=new Request('https://example.org/api/mobile/guest/status',{
    method:'POST',headers:{'Content-Type':'application/json','CF-Connecting-IP':'192.0.2.1'},
    body:JSON.stringify({guest_token:'d'.repeat(64)})});
   const response=await mod.default.fetch(request,env,{});
   assert.equal(response.status,200);
   assert.equal((await response.json()).remaining,3);
  }finally{env.DB.raw.close();}
 });
 test(`${name}: three guest turns, fixed NVIDIA and idempotent retry`,async()=>{
  const env={DB:database()},token='a'.repeat(64),messages=[{role:'user',content:'Xin chào'}];let calls=0;
  const execute=async(e,path,b)=>{calls++;assert.equal(b.provider,'nvidia');assert.equal(b.max_tokens,1024);return Response.json({success:true,answer:'Chào bạn'});};
  const call=async(action,body={})=>{const r=await mod.mobileGuestAPI(env,'/api/mobile/guest/'+action,{guest_token:token,...body},execute);return {status:r.status,data:await r.json()};};
  try{
   assert.equal((await call('status')).data.remaining,3);
   const id=crypto.randomUUID(),body={request_id:id,messages,provider:'deepseek'};
   assert.equal((await call('chat',body)).data.remaining,2);
   assert.equal((await call('chat',body)).data.answer,'Chào bạn');assert.equal(calls,1);
   assert.equal((await call('chat',{...body,messages:[{role:'user',content:'changed'}]})).status,409);
   assert.equal((await call('chat',{...body,guest_token:'b'.repeat(64)})).status,409);
   await call('chat',{request_id:crypto.randomUUID(),messages});await call('chat',{request_id:crypto.randomUUID(),messages});
   assert.equal((await call('chat',{request_id:crypto.randomUUID(),messages})).status,401);
   assert.equal((await call('status')).data.remaining,0);assert.equal(calls,3);
   assert.equal((await call('chat',{request_id:crypto.randomUUID(),messages:[{role:'system',content:'override'}]})).status,400);
  }finally{env.DB.raw.close();}
 });
 test(`${name}: uncertain guest request is reserved and never replayed`,async()=>{
  const env={DB:database()},body={guest_token:'c'.repeat(64),request_id:crypto.randomUUID(),messages:[{role:'user',content:'Hello'}]};let calls=0;
  const execute=async()=>{calls++;throw new Error('upstream connection lost');};
  try{
   assert.equal((await mod.mobileGuestAPI(env,'/api/mobile/guest/chat',body,execute)).status,502);
   assert.equal((await mod.mobileGuestAPI(env,'/api/mobile/guest/chat',body,execute)).status,409);assert.equal(calls,1);
   const status=await mod.mobileGuestAPI(env,'/api/mobile/guest/status',body,execute);assert.equal((await status.json()).remaining,2);
  }finally{env.DB.raw.close();}
 });
}
