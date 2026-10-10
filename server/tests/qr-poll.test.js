import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import dashboard from '../../work.js';
import server from '../worker.js';

function database(){
 const raw=new DatabaseSync(':memory:'),queries=[];
 return {raw,queries,prepare(sql){queries.push(sql);return {args:[],bind(...args){this.args=args;return this;},async run(){return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){return Promise.all(items.map(item=>item.run()));}};
}
for(const [name,worker] of [['root',dashboard],['server',server]]){
 test(`${name}: QR polling reads only the owned order and never scans usage`,async()=>{
  const env={DB:database(),ADMIN_KEY:'fixture-admin-secret'};
  const call=async(path,body={},user='admin')=>{
   const response=await worker.fetch(new Request('https://example.org'+path,{method:'POST',body:JSON.stringify({...body,username:user,key:user==='admin'?env.ADMIN_KEY:'fixture-password'})}),env,{});
   return {status:response.status,data:await response.json()};
  };
  try{
   await call('/api/billing/status');
   for(const user of ['alice','bob'])env.DB.raw.prepare("INSERT INTO users(username,key,tier,expires_at) VALUES(?,'fixture-password','pro','Vĩnh viễn')").run(user);
   const id=crypto.randomUUID();
   env.DB.raw.prepare("INSERT INTO billing_orders(id,owner,kind,amount,memo,created,expires) VALUES(?,'alice','topup',20000,'fixture',?,?)").run(id,Date.now(),Date.now()+60000);
   env.DB.queries.length=0;
   const pending=await call('/api/billing/order/status',{order_id:id},'alice');
   assert.equal(pending.status,200);assert.equal(pending.data.order_status.status,'pending');
   assert.equal(env.DB.queries.filter(q=>/FROM billing_orders/.test(q)).length,1);
   assert.ok(!env.DB.queries.some(q=>/billing_usage|GROUP BY|billing_wallets|provider_credentials/.test(q)));
   assert.equal((await call('/api/billing/order/status',{order_id:id},'bob')).status,404);
   assert.equal((await call('/api/billing/order/status',{order_id:'invalid'},'alice')).status,400);
   env.DB.raw.prepare('UPDATE billing_orders SET expires=1 WHERE id=?').run(id);
   assert.equal((await call('/api/billing/order/status',{order_id:id},'alice')).data.order_status.status,'expired');
   env.DB.raw.prepare("UPDATE billing_orders SET status='paid' WHERE id=?").run(id);
   assert.equal((await call('/api/billing/order/status',{order_id:id},'alice')).data.order_status.status,'paid');
   assert.equal(env.DB.raw.prepare('SELECT COUNT(*) AS n FROM billing_wallets WHERE owner=?').get('alice').n,0);
  }finally{env.DB.raw.close();}
 });
}
