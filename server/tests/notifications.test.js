import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import dashboard from '../../work.js';
import server from '../worker.js';
function database(){
 const raw=new DatabaseSync(':memory:');
 return {raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){raw.exec('BEGIN');try{const output=[];for(const item of items)output.push(await item.run());raw.exec('COMMIT');return output;}catch(e){raw.exec('ROLLBACK');throw e;}}};
}
for(const [name,worker] of [['root',dashboard],['server',server]]){
 test(`${name}: notifications isolate recipients and persist reads`,async()=>{
  const env={DB:database(),ADMIN_KEY:'fixture-admin-secret'};
  const call=async(path,body={},user='admin')=>{
   const r=await worker.fetch(new Request('https://example.org'+path,{method:'POST',body:JSON.stringify({...body,username:user,key:user==='admin'?env.ADMIN_KEY:'fixture-password'})}),env,{});
   return {status:r.status,data:await r.json()};
  };
  await call('/api/notifications/list');
  for(const user of ['alice','bob'])env.DB.raw.prepare("INSERT INTO users(username,key,fullname,tier,expires_at) VALUES(?,'fixture-password',?,'pro','Vĩnh viễn')").run(user,user);
  const id=crypto.randomUUID();
  assert.equal((await call('/api/admin/notifications/send',{id,title:'Test',text:'Private',target:'alice'},'bob')).status,403);
  assert.equal((await call('/api/admin/notifications/send',{id,title:'Test',text:'Private',target:'alice'})).status,200);
  assert.equal((await call('/api/notifications/list',{},'bob')).data.unread,0);
  assert.equal((await call('/api/notifications/list',{},'alice')).data.unread,1);
  await call('/api/notifications/read',{id},'bob');
  assert.equal((await call('/api/notifications/list',{},'alice')).data.unread,1);
  await call('/api/notifications/read',{id},'alice');
  assert.equal((await call('/api/notifications/list',{},'alice')).data.unread,0);
  assert.equal((await call('/api/admin/notifications/send',{id,title:'Test',text:'Private',target:'alice'})).status,200);
  assert.equal((await call('/api/notifications/list',{},'alice')).data.notifications.length,1);
 });
}
