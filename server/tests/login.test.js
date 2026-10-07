import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import worker from '../worker.js';

function binding(raw,trace,options={}){
 return {prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async first(){trace.push(sql);return raw.prepare(sql).get(...this.args)||null;},async all(){trace.push(sql);return {results:raw.prepare(sql).all(...this.args)};},async run(){trace.push(sql);if(options.failMigration&&sql.includes('CREATE TABLE IF NOT EXISTS admin_audit'))throw Error('fixture migration failure');return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};}};},async batch(items){
  if(options.beforeBatch)options.beforeBatch(items);
  raw.exec('BEGIN');try{const results=[];for(const item of items)results.push(await item.run());raw.exec('COMMIT');return results;}catch(e){raw.exec('ROLLBACK');throw e;}
 }};
}
function request(username,key){return new Request('https://example.workers.dev/api/login',{method:'POST',headers:{'Content-Type':'application/json','CF-Connecting-IP':'192.0.2.55'},body:JSON.stringify({username,key,device_id:'fixture-device'})});}
const secret='fixture-admin-secret-32-characters';

test('cold login migrates once; new D1 binding uses persisted version without DDL',async()=>{
 const raw=new DatabaseSync(':memory:'),trace=[];
 let env={DB:binding(raw,trace),ADMIN_KEY:secret};
 const first=await worker.fetch(request('admin',secret),env,{});assert.equal(first.status,200);assert.equal((await first.json()).first_login,true);
 const initial=trace.length;assert.ok(initial>15);
 trace.length=0;env={...env,DB:binding(raw,trace)}; // distinct object simulates a cold isolate
 const second=await worker.fetch(request('admin',secret),env,{});assert.equal(second.status,200);assert.equal((await second.json()).first_login,false);
 assert.equal(trace.filter(sql=>/CREATE|ALTER|PRAGMA/.test(sql)).length,0);
 assert.ok(trace.length<=4,`Expected <=4 SQL statements; got ${trace.length}`);
 raw.close();
});

test('migration failures never publish readiness; retry repairs schema',async()=>{
 const raw=new DatabaseSync(':memory:'),trace=[];
 let env={DB:binding(raw,trace,{failMigration:true}),ADMIN_KEY:secret};
 assert.equal((await worker.fetch(request('admin',secret),env,{})).status,503);
 assert.equal(raw.prepare("SELECT name FROM sqlite_master WHERE name='chat_ai_runtime_schema'").get(),undefined);
 env={...env,DB:binding(raw,trace)};
 assert.equal((await worker.fetch(request('admin',secret),env,{})).status,200);
 raw.prepare('UPDATE chat_ai_runtime_schema SET version=0').run();
 trace.length=0;env={...env,DB:binding(raw,trace)};
 assert.equal((await worker.fetch(request('admin',secret),env,{})).status,200);
 assert.ok(trace.some(sql=>sql.includes('PRAGMA')));
 assert.equal(raw.prepare('SELECT version FROM chat_ai_runtime_schema').get().version,1);
 raw.close();
});

test('fast login still enforces password, expiry, status and revoked session tokens',async()=>{
 const raw=new DatabaseSync(':memory:'),trace=[],env={DB:binding(raw,trace),ADMIN_KEY:secret};
 await worker.fetch(request('admin',secret),env,{});
 raw.prepare("INSERT INTO users(username,key,fullname,tier,expires_at) VALUES('alice','fixture-password','Alice','pro','Vĩnh viễn')").run();
 const response=await worker.fetch(request('alice','fixture-password'),env,{});assert.equal(response.status,200);
 const data=await response.json();assert.ok(data.session_token.startsWith('session:'));
 assert.equal(raw.prepare('SELECT COUNT(*) AS n FROM account_tokens').get().n,1);
 assert.equal(raw.prepare('SELECT device_id FROM device_logins WHERE username=?').get('alice').device_id,'fixture-device');
 assert.equal((await worker.fetch(request('alice','wrong-password'),env,{})).status,401);
 raw.prepare("UPDATE users SET account_status='disabled' WHERE username='alice'").run();
 assert.equal((await worker.fetch(request('alice',data.session_token),env,{})).status,401);
 raw.prepare("UPDATE users SET account_status='active',session_epoch=1 WHERE username='alice'").run();
 assert.equal((await worker.fetch(request('alice',data.session_token),env,{})).status,401);
 raw.prepare("UPDATE users SET expires_at='2000-01-01' WHERE username='alice'").run();
 assert.equal((await worker.fetch(request('alice','fixture-password'),env,{})).status,401);
 assert.equal((await worker.fetch(request('admin','wrong'),env,{})).status,401);
 raw.close();
});

test('epoch changes during login cannot issue a token or replace device lock',async()=>{
 const raw=new DatabaseSync(':memory:'),trace=[];
 let env={DB:binding(raw,trace),ADMIN_KEY:secret};
 await worker.fetch(request('admin',secret),env,{});
 raw.prepare("INSERT INTO users(username,key,tier,expires_at) VALUES('alice','fixture-password','pro','Vĩnh viễn')").run();
 raw.prepare("INSERT INTO device_logins(username,device_id,created_at) VALUES('alice','previous-device','fixture')").run();
 env={...env,DB:binding(raw,trace,{beforeBatch(items){
  if(items.length===3&&items[0].args.length===4)raw.prepare("UPDATE users SET session_epoch=session_epoch+1 WHERE username='alice'").run();
 }})};
 assert.equal((await worker.fetch(request('alice','fixture-password'),env,{})).status,401);
 assert.equal(raw.prepare('SELECT COUNT(*) AS n FROM account_tokens').get().n,0);
 assert.equal(raw.prepare("SELECT device_id FROM device_logins WHERE username='alice'").get().device_id,'previous-device');
 raw.close();
});
