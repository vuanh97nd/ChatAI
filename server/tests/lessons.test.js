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
 test(`${name}: unlimited paginated lessons, private isolation and admin shared training`,async()=>{
  const env={DB:database(),ADMIN_KEY:'fixture-admin-secret'};
  const call=async(path,body={},user='admin')=>{
   const r=await worker.fetch(new Request('https://example.org'+path,{method:'POST',body:JSON.stringify({...body,username:user,key:user==='admin'?env.ADMIN_KEY:'fixture-password'})}),env,{});
   return {status:r.status,data:await r.json()};
  };
  await call('/api/lessons/list');
  for(const user of ['alice','bob'])env.DB.raw.prepare("INSERT INTO users(username,key,fullname,tier,expires_at) VALUES(?,'fixture-password',?,'pro','Vĩnh viễn')").run(user,user);
  const record=i=>({id:i.toString(16).padStart(64,'0'),tool:'plaxis_commands',task:'PLAXIS private task',arguments:JSON.stringify({index:i,password:'sensitive',path:'C:/private/model.p2dx'}),evidence:'command accepted',updated:new Date().toISOString(),outcome:'success',level:'command',environment:'PLAXIS 2D 22.1',resolves:[]});
  for(let offset=0;offset<135;offset+=10){
   const records=Array.from({length:Math.min(10,135-offset)},(_,i)=>record(offset+i+1));
   assert.equal((await call('/api/lessons/put',{scope:'private',records},'alice')).status,200);
  }
  let cursor=0,items=[];
  do{const result=await call('/api/lessons/list',{cursor},'alice');assert.equal(result.status,200);items.push(...result.data.items);cursor=result.data.cursor;if(!result.data.has_more)break;}while(true);
  assert.equal(items.length,135);assert.ok(!JSON.stringify(items).includes('sensitive'));
  assert.equal((await call('/api/lessons/list',{},'bob')).data.items.length,0);
  assert.equal((await call('/api/lessons/put',{scope:'shared',records:[record(200)]},'alice')).status,403);
  assert.equal((await call('/api/lessons/put',{scope:'shared',records:[record(200)]})).status,200);
  let shared=await call('/api/lessons/list',{},'bob');assert.equal(shared.data.items.length,1);
  assert.equal(shared.data.items[0].scope,'shared');assert.ok(!JSON.stringify(shared.data.items).includes('private'));
  const sharedCursor=shared.data.cursor;
  assert.equal((await call('/api/admin/lessons/withdraw',{id:record(200).id},'bob')).status,403);
  assert.equal((await call('/api/admin/lessons/withdraw',{id:record(200).id})).status,200);
  shared=await call('/api/lessons/list',{cursor:sharedCursor},'bob');assert.equal(shared.data.items[0].deleted,true);
  const changed=record(1);changed.evidence='fixed';changed.level='model';
  assert.equal((await call('/api/lessons/put',{scope:'private',records:[changed]},'alice')).status,200);
  const update=await call('/api/lessons/list',{cursor},'alice');assert.ok(update.data.items.some(r=>r.record.evidence==='fixed'));
  const search=await call('/api/lessons/search',{query:'PLAXIS'},'alice');assert.equal(search.status,200);assert.ok(search.data.items.length<=20);
  assert.equal((await call('/api/lessons/list',{cursor:-1},'alice')).status,400);
  assert.equal((await call('/api/lessons/put',{scope:'private',records:[{...changed,arguments:'[]'}]},'alice')).status,400);
 });
}
