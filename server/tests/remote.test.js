import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import * as root from '../../work.js';
import * as server from '../worker.js';
function database(){
 const raw=new DatabaseSync(':memory:');
 return {raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){return Promise.all(items.map(item=>item.run()));}};
}
for(const [name,mod] of [['root',root],['server',server]]){
 test(`${name}: pairing is approved, account-scoped, secret-bound, and revocable`,async()=>{
  const env={DB:database()},owner={username:'alice'},desktop=crypto.randomUUID(),mobile=crypto.randomUUID(),secret='a'.repeat(64);
  const request=new Request('https://example.org/api/remote');
  const call=async(action,body={},actor=owner)=>{const response=await mod.remoteAPI(env,actor,'/api/remote/'+action,body,request);return {status:response.status,data:await response.json()};};
  try{
   const device=(await call('desktop/register',{desktop_id:desktop,name:'Office PC'})).data;
   const pc={desktop_id:desktop,desktop_secret:device.desktop_secret};
   assert.equal((await call('desktop/register',{desktop_id:desktop,name:'Steal'}, {username:'bob'})).status,403);
   const offer=(await call('desktop/pair',pc)).data;const qr=JSON.parse(offer.qr);
   const phone={desktop_id:desktop,mobile_id:mobile,mobile_secret:secret};
   assert.equal((await call('pair/request',{...phone,code:qr.code,name:'Phone'}, {username:'bob'})).status,404);
   assert.equal((await call('pair/request',{...phone,code:qr.code,name:'Phone'})).status,200);
   assert.equal((await call('mobile/status',phone)).status,403);
   await call('desktop/approve',{...pc,pair_id:offer.pair_id,approve:true});
   assert.equal((await call('pair/status',{...phone,pair_id:offer.pair_id})).data.state,'approved');
   assert.equal((await call('mobile/status',phone)).status,200);
   assert.equal((await call('mobile/status',{...phone,mobile_secret:'b'.repeat(64)})).status,403);
   await call('desktop/revoke',{...pc,mobile_id:mobile});
   assert.equal((await call('mobile/status',phone)).status,403);
  }finally{env.DB.raw.close();}
 });
 test(`${name}: tasks are idempotent and leased once, with safe pause/resume and offline recovery`,async()=>{
  const env={DB:database()},actor={username:'alice'},desktop=crypto.randomUUID(),mobile=crypto.randomUUID();
  const call=async(action,body={})=>{const r=await mod.remoteAPI(env,actor,'/api/remote/'+action,body,new Request('https://example.org'));return {status:r.status,data:await r.json()};};
  try{
   const device=(await call('desktop/register',{desktop_id:desktop,name:'PC'})).data;
   const pc={desktop_id:desktop,desktop_secret:device.desktop_secret};
   const offer=(await call('desktop/pair',pc)).data;const qr=JSON.parse(offer.qr);
   const phone={desktop_id:desktop,mobile_id:mobile,mobile_secret:'c'.repeat(64)};
   await call('pair/request',{...phone,code:qr.code,name:'Phone'});
   await call('desktop/approve',{...pc,pair_id:offer.pair_id,approve:true});
   const id=crypto.randomUUID(),body={...phone,task_id:id,prompt:'Mở GeoStudio'};
   await call('mobile/send',body);await call('mobile/send',body);
   assert.equal(env.DB.raw.prepare('SELECT COUNT(*) AS n FROM remote_tasks').get().n,1);
   assert.equal((await call('mobile/send',{...body,prompt:'different'})).status,409);
   assert.equal((await call('desktop/tick',{...pc,ready:true})).data.task,null); // disabled until opt in
   await call('desktop/enable',{...pc,enabled:true});
   const first=(await call('desktop/tick',{...pc,ready:true})).data.task;
   assert.equal(first.id,id);
   assert.equal((await call('desktop/tick',{...pc,ready:true})).data.task,null);
   const update={id,lease_id:first.lease_id,state:'running',progress:'Reading',result:'',version:1};
   await call('desktop/tick',{...pc,ready:false,update});
   await call('mobile/control',{...phone,task_id:id,action:'pause'});
   assert.equal((await call('desktop/tick',{...pc,ready:false})).data.active.command,'pause');
   await call('desktop/tick',{...pc,ready:false,update:{...update,state:'paused',version:2,ack:'pause'}});
   assert.equal((await call('desktop/tick',{...pc,ready:false})).data.active.command,null);
   await call('mobile/control',{...phone,task_id:id,action:'resume'});
   await call('desktop/tick',{...pc,ready:false,update:{...update,state:'running',version:3,ack:'resume'}});
   // stale updates cannot undo newer state
   await call('desktop/tick',{...pc,ready:false,update:{...update,state:'paused',version:2}});
   assert.equal((await call('mobile/status',phone)).data.tasks[0].state,'running');
   env.DB.raw.prepare('UPDATE remote_tasks SET lease_until=1 WHERE id=?').run(id);
   assert.equal((await call('mobile/status',phone)).data.tasks[0].connection_lost,true);
   assert.equal((await call('desktop/tick',{...pc,ready:true})).data.task,null); // never requeued
   await call('desktop/tick',{...pc,ready:false,update:{...update,state:'completed',result:'Done',version:4}});
   assert.equal((await call('mobile/status',phone)).data.tasks[0].result,'Done');
   assert.equal((await call('mobile/control',{...phone,task_id:id,action:'resume'})).status,409);
  }finally{env.DB.raw.close();}
 });
}
for(const [name,mod] of [['root',root],['server',server]]){
 test(`${name}: Android companion login does not replace desktop device lock`,async()=>{
  const env={DB:database(),ADMIN_KEY:'fixture-admin-secret'};
  const call=async(path,body)=>{const r=await mod.default.fetch(new Request('https://example.org'+path,{method:'POST',body:JSON.stringify(body)}),env,{});return {status:r.status,data:await r.json()};};
  try{
   await call('/api/billing/status',{username:'admin',key:env.ADMIN_KEY});
   assert.equal((await call('/api/register',{username:'alice',key:'fixture-password',fullname:'Alice',email:'alice@example.org'})).status,201);
   const desktopLogin=await call('/api/login',{username:'alice',key:'fixture-password',device_id:'desktop-id'});
   assert.equal(desktopLogin.status,200);
   const phone=await call('/api/login',{username:'alice',key:'fixture-password',device_id:'phone-id',client_type:'android_companion'});
   assert.equal(phone.status,200);
   assert.equal(env.DB.raw.prepare('SELECT device_id FROM device_logins WHERE username=?').get('alice').device_id,'desktop-id');
   assert.equal((await call('/api/logout',{username:'alice',key:phone.data.session_token,client_type:'android_companion'})).status,200);
   assert.equal(env.DB.raw.prepare('SELECT device_id FROM device_logins WHERE username=?').get('alice').device_id,'desktop-id');
  }finally{env.DB.raw.close();}
 });
}
