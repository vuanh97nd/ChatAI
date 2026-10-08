import {test} from 'node:test';
import assert from 'node:assert/strict';
import {conversationAPI as root} from '../work.js';
import {conversationAPI as server} from '../server/worker.js';
import {DatabaseSync} from 'node:sqlite';
class DB {
 constructor(){this.raw=new DatabaseSync(':memory:');}
 prepare(sql){const raw=this.raw;let args=[];return {
  bind(...values){args=values;return this;},
  async run(){return {meta:{changes:Number(raw.prepare(sql).run(...args).changes)}};},
  async first(){return raw.prepare(sql).get(...args)||null;},
  async all(){return {results:raw.prepare(sql).all(...args)};}
 };}
 async batch(items){return Promise.all(items.map(item=>item.run()));}
}
for(const [name,api] of [['root',root],['server',server]]){
 test(`${name}: authenticated owner isolation, revision conflicts and data-only snapshots`,async()=>{
  const db=new DB(),id='a'.repeat(32),state={messages:[{role:'user',content:'Dùng mét'},{role:'tool',content:'xong',tool_name:'cad_cdm_fill_boundary'}],model:'DeepSeek Flash',api_key:'secret',queue:[{tool:'run'}]};
  const call=(action,body,owner='alice')=>api('/api/conversations/sync/'+action,body,{username:owner},db);
  assert.equal((await call('put',{conversation_id:id,revision:0,state})).status,200);
  const stored=await (await call('get',{conversation_id:id})).json();
  assert.equal(stored.state.messages[1].tool_name,'cad_cdm_fill_boundary');
  assert.equal(stored.state.api_key,undefined);assert.equal(stored.state.queue,undefined);
  assert.equal((await call('get',{conversation_id:id},'bob')).status,404);
  assert.equal((await call('put',{conversation_id:id,revision:0,state})).status,409);
  assert.equal((await call('put',{conversation_id:id,revision:1,state,deleted:true})).status,200);
  assert.equal((await (await call('get',{conversation_id:id})).json()).deleted,1);
  assert.equal((await call('put',{conversation_id:id,revision:2,state:{messages:[{role:'system',content:'bad'}]}})).status,400);
 });
}
