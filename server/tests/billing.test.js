import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import dashboard from '../../work.js';
import server from '../worker.js';
function database(){
 const raw=new DatabaseSync(':memory:');
 return {raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){raw.exec('BEGIN');try{const output=[];for(const item of items)output.push(await item.run());raw.exec('COMMIT');return output;}catch(e){raw.exec('ROLLBACK');throw e;}}};
}
for(const [name,worker] of [['dashboard',dashboard],['server',server]]){
 test(`${name}: QR, trial, manual credits, authoritative usage and free NVIDIA`,async()=>{
  const env={DB:database(),ADMIN_KEY:'fixture-admin-secret-32-characters',DEEPSEEK_API_KEY:'fixture-deepseek-key',NVIDIA_API_KEY:'fixture-nvidia-key'};
  const secret='fixture-webhook-secret-32-characters';
  const call=async(path,body={},user='admin',headers={})=>{
   const response=await worker.fetch(new Request('https://example.workers.dev'+path,{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify({...body,...(user?{username:user,key:user==='admin'?env.ADMIN_KEY:'fixture-password'}:{})})}),env,{});
   return {status:response.status,value:response.headers.get('Content-Type')?.includes('text/event-stream')?await response.text():await response.json()};
  };
  const original=globalThis.fetch;let calls=0;
  try{
   assert.equal((await call('/api/billing/status')).status,200);
   env.DB.raw.prepare("INSERT INTO users(username,key,tier,expires_at,created_at) VALUES('alice','fixture-password','trial','Vĩnh viễn',?)").run(new Date().toISOString());
   env.DB.raw.prepare("INSERT INTO users(username,key,tier,expires_at) VALUES('other','fixture-password','pro','Vĩnh viễn')").run();
   let r=await call('/api/admin/billing/config/save',{config:{enabled:true,bank:'VCB',account:'0123456789',name:'TEST ACCOUNT',secret}});assert.equal(r.status,200,JSON.stringify(r.value));
   r=await call('/api/admin/billing/config/get');assert.equal(r.value.config.secret_configured,true);assert.ok(!JSON.stringify(r.value).includes(secret));
   const saved=env.DB.raw.prepare("SELECT encrypted_value FROM provider_credentials WHERE provider='billing_sepay'").get().encrypted_value;assert.ok(!saved.includes(secret));
   assert.equal((await call('/api/admin/billing/config/get',{},'alice')).status,403);
   const ai={provider:'deepseek_flash',messages:[{role:'user',content:'Xin chào'}]};
   globalThis.fetch=async()=>{calls++;return Response.json({choices:[{message:{content:'OK'},finish_reason:'stop'}],usage:{total_tokens:1000,prompt_tokens:800,completion_tokens:200}});};
   r=await call('/api/provider/model',ai,'alice');assert.equal(r.status,402);assert.equal(calls,0);
   r=await call('/api/billing/status',{},'alice');assert.equal(r.value.wallet.service_active,true);assert.equal(r.value.wallet.balance_vnd,0);assert.ok(r.value.wallet.trial_until>Date.now()+29*86400000);
   r=await call('/api/billing/order',{kind:'topup',amount:12345,request_id:crypto.randomUUID()},'alice');assert.equal(r.status,400);
   const id=crypto.randomUUID();r=await call('/api/billing/order',{kind:'topup',amount:20000,request_id:id},'alice');assert.equal(r.status,200);const order=r.value.order;
   assert.ok(r.value.qr_url.includes('amount=20000'));assert.ok(r.value.qr_url.includes(order.memo));
   const orderRetry=await call('/api/billing/order',{kind:'topup',amount:20000,request_id:id},'alice');assert.equal(orderRetry.value.order.memo,order.memo);
   const tx={id:123456,transferType:'in',accountNumber:'0123456789',content:order.memo,transferAmount:20000};
   const hook=(body=tx,token=secret)=>call('/api/billing/webhook',body,null,{Authorization:'Apikey '+token});
   assert.equal((await hook(tx,'fake-secret')).status,401);
   assert.equal((await hook({...tx,accountNumber:'9999999999'})).status,400);
   assert.equal((await hook({...tx,transferAmount:19000})).value.matched,false);
   assert.equal((await hook({...tx,transferType:'out'})).value.matched,false);
   assert.equal((await hook()).value.matched,true);assert.equal((await hook()).value.matched,true);
   assert.equal((await hook({...tx,id:123457})).value.matched,true);
   r=await call('/api/billing/status',{},'alice');assert.equal(r.value.wallet.balance_vnd,20000);
   r=await call('/api/billing/status',{target:'alice'},'other');assert.equal(r.value.wallet.owner,'other');assert.equal(r.value.orders.length,0);
   r=await call('/api/provider/model',ai,'alice');assert.equal(r.status,200,JSON.stringify(r.value));
   r=await call('/api/billing/status',{},'alice');assert.equal(r.value.wallet.balance_vnd,19996);assert.equal(r.value.wallet.held_vnd,0);assert.equal(r.value.usage[0].tokens,1000);
   globalThis.fetch=async()=>Response.json({choices:[{message:{content:'',reasoning_content:'thinking'},finish_reason:'length'}],usage:{total_tokens:1000}});
   r=await call('/api/provider/model',ai,'alice');assert.equal(r.status,502);assert.equal(r.value.code,'AI_OUTPUT_LIMIT');
   r=await call('/api/billing/status',{},'alice');assert.equal(r.value.wallet.balance_vnd,19992);
   // Missing usage is never fabricated or silently refunded after successful generation.
   globalThis.fetch=async()=>Response.json({choices:[{message:{content:'OK'}}]});
   r=await call('/api/provider/model',ai,'alice');assert.equal(r.value.code,'BILLING_USAGE_PENDING');
   r=await call('/api/billing/status',{},'alice');assert.ok(r.value.wallet.held_vnd>0);
   const pending=r.value.usage.find(u=>u.state==='pending_review');
   assert.equal((await call('/api/admin/billing/reconcile',{id:pending.id,tokens:120,note:'Đối chiếu usage'},'alice')).status,403);
   assert.equal((await call('/api/admin/billing/reconcile',{id:pending.id,tokens:120,note:'Đối chiếu usage'})).status,200);
   assert.equal((await call('/api/admin/billing/reconcile',{id:pending.id,tokens:120,note:'Lặp lại'})).status,409);
   const creditId=crypto.randomUUID(),credit={target:'alice',amount:50000,note:'Chứng từ thủ công',request_id:creditId};
   assert.equal((await call('/api/admin/billing/credit',credit,'alice')).status,403);
   assert.equal((await call('/api/admin/billing/credit',credit)).status,200);
   assert.equal((await call('/api/admin/billing/credit',credit)).status,200);
   r=await call('/api/billing/status',{},'alice');assert.equal(r.value.wallet.balance_vnd,69991.52);assert.equal(r.value.wallet.held_vnd,0);
   env.DB.raw.prepare("UPDATE billing_wallets SET trial_until=?,service_until=0,balance=0 WHERE owner='alice'").run(Date.now()-86400000);
   assert.equal((await call('/api/provider/model',ai,'alice')).value.code,'SERVICE_EXPIRED');
   // NVIDIA bypasses both subscription and wallet checks.
   assert.equal((await call('/api/provider/model',{...ai,provider:'nvidia'},'alice')).status,200);
   assert.equal((await call('/api/provider/model',ai)).status,200); // admin exempt
   r=await call('/api/billing/order',{kind:'service',amount:100000,request_id:crypto.randomUUID()},'alice');const renewal=r.value.order;
   assert.equal((await hook({...tx,id:123458,content:renewal.memo,transferAmount:100000})).value.matched,true);
   r=await call('/api/billing/status',{},'alice');assert.equal(r.value.wallet.service_active,true);assert.equal(r.value.wallet.balance_vnd,0);
   assert.equal((await call('/api/provider/model',ai,'alice')).value.code,'TOKEN_BALANCE_LOW');
   env.DB.raw.prepare("UPDATE users SET expires_at='2000-01-01' WHERE username='alice'").run();
   assert.equal((await call('/api/billing/status',{},'alice')).status,200); // renewal accessible
   await call('/api/admin/accounts/action',{target:'alice',action:'lock'});
   // The authenticated account lock cannot be bypassed through billing endpoints.
   env.DB.raw.prepare("UPDATE users SET account_status='locked' WHERE username='alice'").run();
   assert.equal((await call('/api/billing/status',{},'alice')).status,401);
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });
 test(`${name}: expired or replayed bank receipts cannot credit another order`,async()=>{
  const env={DB:database(),ADMIN_KEY:'fixture-admin-secret-32-characters'};
  const call=async(path,body,webhook=false)=>{
   const r=await worker.fetch(new Request('https://example.org'+path,{method:'POST',headers:{'Content-Type':'application/json',...(webhook?{Authorization:'Apikey fixture-webhook-secret-32-characters'}:{})},body:JSON.stringify(webhook?body:{...body,username:'admin',key:env.ADMIN_KEY})}),env,{});return {status:r.status,data:await r.json()};
  };
  try{
   await call('/api/admin/billing/config/save',{config:{enabled:true,bank:'VCB',account:'0123456789',name:'TEST',secret:'fixture-webhook-secret-32-characters'}});
   env.DB.raw.prepare("INSERT INTO billing_wallets(owner,trial_until) VALUES('alice',?)").run(Date.now());
   const insert=env.DB.raw.prepare("INSERT INTO billing_orders(id,owner,kind,amount,memo,created,expires) VALUES(?,'alice','topup',20000,?,?,?)");
   insert.run('one','CA11111111111111111111',Date.now(),Date.now()+60000);
   insert.run('two','CA22222222222222222222',Date.now(),Date.now()+60000);
   insert.run('expired','CA33333333333333333333',Date.now(),Date.now()-1000);
   const tx={id:'unique',transferType:'in',accountNumber:'0123456789',content:'CA11111111111111111111',transferAmount:20000};
   assert.equal((await call('/api/billing/webhook',tx,true)).data.matched,true);
   assert.equal((await call('/api/billing/webhook',{...tx,content:'CA22222222222222222222'},true)).data.matched,false);
   assert.equal((await call('/api/billing/webhook',{...tx,id:'expired',content:'CA33333333333333333333'},true)).data.matched,false);
   assert.equal(env.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='alice'").get().balance,20000000);
  }finally{env.DB.raw.close();}
 });
}

for(const [name,worker] of [['dashboard',dashboard],['server',server]]){
 test(`${name}: paid SSE settles before delivery; unknown and unsent requests are distinguished`,async()=>{
  const env={DB:database(),ADMIN_KEY:'fixture-admin-secret-32-characters',DEEPSEEK_API_KEY:'fixture-deepseek-key',NVIDIA_API_KEY:'fixture-nvidia-key',OPENAI_API_KEY:'fixture-openai-key'};
  const call=(path,body={},username='admin')=>worker.fetch(new Request('https://example.org'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,key:username==='admin'?env.ADMIN_KEY:'fixture-password',...body})}),env,{});
  const original=globalThis.fetch;
  try{
   await call('/api/admin/billing/config/save',{config:{enabled:true,bank:'VCB',account:'0123456789',name:'Test',secret:'fixture-webhook-secret-32-characters'}});
   env.DB.raw.prepare("INSERT INTO users(username,key,tier,expires_at) VALUES('alice','fixture-password','pro','Vĩnh viễn')").run();
   await call('/api/admin/billing/credit',{target:'alice',amount:20000,note:'Test',request_id:crypto.randomUUID()});
   const body={provider:'deepseek_flash',messages:[{role:'user',content:'Hi'}],stream:true};
   let upstream;
   globalThis.fetch=async(url,options)=>{upstream=JSON.parse(options.body);return Response.json({choices:[{message:{content:'Full answer'},finish_reason:'stop'}],usage:{total_tokens:250}});};
   let response=await call('/api/provider/model',body,'alice');assert.equal(response.status,200);assert.equal(upstream.stream,false);
   assert.equal(env.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='alice'").get().balance,19999000);
   assert.match(await response.text(),/Full answer/);
   globalThis.fetch=async()=>{throw Error('connection reset');};
   response=await call('/api/provider/model',{...body,stream:false},'alice');assert.equal((await response.json()).code,'BILLING_USAGE_PENDING');
   let wallet=env.DB.raw.prepare("SELECT * FROM billing_wallets WHERE owner='alice'").get();const held=wallet.held;assert.ok(held>0);
   delete env.DEEPSEEK_API_KEY;
   response=await call('/api/provider/model',{...body,stream:false},'alice');assert.equal(response.status,503);
   wallet=env.DB.raw.prepare("SELECT * FROM billing_wallets WHERE owner='alice'").get();assert.equal(wallet.held,held); // no extra hold for missing key
   response=await call('/api/provider/model',{...body,provider:'openai',stream:false},'alice');assert.equal((await response.json()).code,'OPENAI_PRICING_UNSET');
   globalThis.fetch=async(url,options)=>{assert.equal(url,'https://api.openai.com/v1/chat/completions');assert.equal(JSON.parse(options.body).model,'gpt-4.1-mini');return Response.json({choices:[{message:{content:'OK'}}],usage:{total_tokens:125}});};
   response=await call('/api/provider/model',{...body,provider:'openai',stream:false});assert.equal(response.status,200);
   const audit=env.DB.raw.prepare("SELECT tokens,charged,state FROM billing_usage WHERE owner='admin'").get();assert.equal(audit.tokens,125);assert.equal(audit.charged,0);assert.equal(audit.state,'free');
   // Both accounting and access gates remain server-side on legacy endpoints.
   response=await call('/api/chat/stream',{provider:'deepseek',text:'Hi'},'alice');assert.equal(response.status,402);
   // In-flight holds from a crashed Worker become reviewable, never silently refunded.
   env.DB.raw.prepare("UPDATE billing_usage SET state='reserved',created=? WHERE owner='alice' AND state='pending_review'").run(Date.now()-181000);
   await call('/api/billing/status',{},'alice');
   assert.equal(env.DB.raw.prepare("SELECT COUNT(*) AS n FROM billing_usage WHERE owner='alice' AND state='pending_review'").get().n,1);
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });
}
