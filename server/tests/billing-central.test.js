import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import dashboard from '../../work.js';
import server from '../worker.js';

function database(){
 const raw=new DatabaseSync(':memory:');
 return {raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){raw.exec('BEGIN');try{const output=[];for(const item of items)output.push(await item.run());raw.exec('COMMIT');return output;}catch(error){raw.exec('ROLLBACK');throw error;}}};
}
for(const [name,worker] of [['dashboard',dashboard],['server',server]]){
 test(`${name}: frozen ledger migration preserves money/history and refuses overwrite`,async()=>{
  const mainOrigin='https://main.example.org',backupOrigin='https://backup.example.org';
  const link='fixture-link-secret-more-than-32-chars';
  const main={DB:database(),ADMIN_KEY:'fixture-main-admin-secret',DEEPSEEK_API_KEY:'fixture-provider-key',BILLING_ROLE:'local',BILLING_AUTHORITY_URL:backupOrigin,BILLING_PUBLIC_ORIGIN:mainOrigin,BILLING_LINK_KEY:link,BILLING_ACCOUNT_MAP:JSON.stringify({alice:'ledgeralice'})};
  const backup={DB:database(),ADMIN_KEY:'fixture-backup-admin-secret',BILLING_ROLE:'authority',BILLING_PRIMARY_URL:mainOrigin,BILLING_LINK_KEY:link,BILLING_MIGRATION_FREEZE:'true'};
  const call=async(env,origin,path,body={},username='admin')=>{
   const response=await worker.fetch(new Request(origin+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,username,key:username==='admin'?env.ADMIN_KEY:'fixture-password'})}),env,{});
   return {status:response.status,value:await response.json()};
  };
  const original=globalThis.fetch;
  globalThis.fetch=async(input,options)=>String(input).startsWith(backupOrigin)?worker.fetch(new Request(input,options),backup,{}):Response.json({choices:[{message:{content:'OK'},finish_reason:'stop'}],usage:{total_tokens:1000}});
  try{
   const config={enabled:true,service_fee:0,token_price:4000,bank:'VCB',account:'0123456789',name:'FIXTURE',secret:'fixture-original-bank-secret-32-chars'};
   assert.equal((await call(main,mainOrigin,'/api/admin/billing/config/save',{config})).status,200);
   main.DB.raw.prepare("INSERT INTO users(username,key,tier,expires_at,created_at) VALUES('alice','fixture-password','pro','Vĩnh viễn',?)").run(new Date().toISOString());
   assert.equal((await call(main,mainOrigin,'/api/admin/billing/credit',{target:'alice',amount:20000,note:'original balance',request_id:crypto.randomUUID()})).status,200);
   const ai={provider:'deepseek_flash',messages:[{role:'user',content:'hello'}]};
   assert.equal((await call(main,mainOrigin,'/api/provider/model',ai,'alice')).status,200);
   main.BILLING_ROLE='primary';main.BILLING_MIGRATION_FREEZE='true';
   const payload={confirm:'MIGRATE_BILLING_TO_BACKUP',request_id:crypto.randomUUID()};
   assert.equal((await call(main,mainOrigin,'/api/provider/model',ai,'alice')).value.code,'BILLING_MIGRATION_FREEZE');
   assert.equal((await call(main,mainOrigin,'/api/billing/order',{kind:'topup',amount:20000,request_id:crypto.randomUUID()},'alice')).status,503);
   const r=await call(main,mainOrigin,'/api/admin/billing/central-migration',payload);assert.equal(r.status,200,JSON.stringify(r.value));
   assert.equal(backup.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='ledgeralice'").get().balance,19996000);
   assert.equal(backup.DB.raw.prepare('SELECT count(*) AS n FROM billing_usage').get().n,1);
   assert.equal((await call(main,mainOrigin,'/api/admin/billing/central-migration',payload)).value.already_imported,true);
   assert.equal((await call(main,mainOrigin,'/api/admin/billing/central-migration',{...payload,request_id:crypto.randomUUID()})).status,409);
   assert.equal((await call(main,mainOrigin,'/api/admin/billing/central-migration',payload,'alice')).status,403);
   main.BILLING_MIGRATION_FREEZE='false';backup.BILLING_MIGRATION_FREEZE='false';
   assert.equal((await call(main,mainOrigin,'/api/provider/model',ai,'alice')).status,200);
   assert.equal(backup.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='ledgeralice'").get().balance,19992000);
   assert.equal(backup.DB.raw.prepare('SELECT count(*) AS n FROM billing_usage').get().n,2);
   assert.equal(main.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='alice'").get().balance,19996000,'legacy source preserved, no longer spent');
  }finally{globalThis.fetch=original;}
 });
 test(`${name}: central deposits, offline spending bound, reconnect and idempotent settlement`,async()=>{
  const mainOrigin='https://main.example.org',backupOrigin='https://backup.example.org';
  const link='fixture-link-secret-more-than-32-chars';
  const main={DB:database(),ADMIN_KEY:'fixture-main-admin-secret',DEEPSEEK_API_KEY:'fixture-provider-key',BILLING_ROLE:'primary',BILLING_AUTHORITY_URL:backupOrigin,BILLING_PUBLIC_ORIGIN:mainOrigin,BILLING_LINK_KEY:link,BILLING_ACCOUNT_MAP:JSON.stringify({alice:'ledgeralice'})};
  const backup={DB:database(),ADMIN_KEY:'fixture-backup-admin-secret',BILLING_ROLE:'authority',BILLING_PRIMARY_URL:mainOrigin,BILLING_LINK_KEY:link};
  const call=async(env,origin,path,body={},username='admin')=>{
   const response=await worker.fetch(new Request(origin+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,username,key:username==='admin'?env.ADMIN_KEY:'fixture-alice-password'})}),env,{});
   return {status:response.status,value:await response.json()};
  };
  const original=globalThis.fetch;let offline=false,modelCalls=0,lastEnvelope,dropGrant=false,unknownUsage=false;
  globalThis.fetch=async(input,options)=>{
   const url=String(input);
   if(url.startsWith(backupOrigin)){
    if(offline)throw new TypeError('fixture outage');
    assert.ok(!options.body.includes(main.ADMIN_KEY));assert.ok(!options.body.includes('fixture-alice-password'));assert.ok(!options.body.includes(main.DEEPSEEK_API_KEY));
    lastEnvelope={url,options};
    const response=await worker.fetch(new Request(url,options),backup,{});
    const message=JSON.parse(options.body);
    if(dropGrant&&message.action==='sync'&&message.payload.allocate){dropGrant=false;throw new TypeError('lost committed allocation reply');}
    return response;
   }
   assert.equal(url,'https://api.deepseek.com/chat/completions');
   assert.equal(options.headers.Authorization,'Bearer '+main.DEEPSEEK_API_KEY);
   modelCalls++;
   return Response.json({choices:[{message:{content:'OK'},finish_reason:'stop'}],...(!unknownUsage?{usage:{total_tokens:1000,prompt_tokens:800,completion_tokens:200}}:{})});
  };
  try{
   assert.equal((await call(backup,backupOrigin,'/api/admin/billing/config/save',{config:{enabled:true,service_fee:0,token_price:4000,bank:'VCB',account:'0123456789',name:'FIXTURE',secret:'fixture-webhook-secret-more-than-32'}})).status,200);
   // Initialize only the primary account. No matching backup login/password exists.
   await call(main,mainOrigin,'/api/billing/status');
   main.DB.raw.prepare("INSERT INTO users(username,key,tier,expires_at,created_at) VALUES('alice','fixture-alice-password','pro','Vĩnh viễn',?)").run(new Date().toISOString());
   offline=true;
   const accounts=await call(main,mainOrigin,'/api/admin/accounts/list');assert.equal(accounts.status,200,'account management remains on primary during billing outage');
   offline=false;
   assert.equal((await call(main,mainOrigin,'/api/admin/billing/credit',{target:'alice',amount:20000,note:'fixture funding',request_id:crypto.randomUUID()})).status,200);
   assert.equal(backup.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='ledgeralice'").get().balance,20000000);
   const ai={provider:'deepseek_flash',messages:[{role:'user',content:'Xin chào'}]};
   // Lost allocation response: money is held centrally but cannot be minted locally.
   dropGrant=true;
   let r=await call(main,mainOrigin,'/api/provider/model',ai,'alice');assert.equal(r.status,402);assert.equal(modelCalls,0);
   assert.equal(backup.DB.raw.prepare("SELECT count(*) AS n FROM billing_allocations WHERE owner='ledgeralice'").get().n,1);
   r=await call(main,mainOrigin,'/api/provider/model',ai,'alice');
   assert.equal(r.status,200,JSON.stringify(r.value));assert.equal(r.value.answer,'OK');
   assert.equal(backup.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='ledgeralice'").get().balance,19996000);
   assert.equal(main.DB.raw.prepare("SELECT balance FROM billing_spend_wallets WHERE owner='alice'").get().balance,19996000);
   assert.equal(main.DB.raw.prepare("SELECT count(*) AS n FROM sqlite_master WHERE type='table' AND name='billing_wallets'").get().n,0,'no primary legacy wallet created');
   r=await call(main,mainOrigin,'/api/billing/status',{},'alice');assert.equal(r.value.wallet.available_vnd,19996);
   // A replay of a signed link message cannot mutate anything.
   const replay=await worker.fetch(new Request(lastEnvelope.url,lastEnvelope.options),backup,{});assert.equal(replay.status,409);
   offline=true;
   r=await call(main,mainOrigin,'/api/billing/order',{kind:'topup',amount:20000,request_id:crypto.randomUUID()},'alice');assert.equal(r.status,503);assert.equal(r.value.code,'BILLING_AUTHORITY_UNAVAILABLE');
   r=await call(main,mainOrigin,'/api/admin/billing/credit',{target:'alice',amount:20000,note:'must fail',request_id:crypto.randomUUID()});assert.equal(r.status,503);
   r=await call(main,mainOrigin,'/api/billing/status',{},'alice');assert.equal(r.status,200);assert.equal(r.value.billing_offline,true);assert.equal(r.value.topups_available,false);assert.equal(r.value.wallet.available_vnd,19996);
   r=await call(main,mainOrigin,'/api/provider/model',ai,'alice');assert.equal(r.status,200);assert.equal(modelCalls,2);
   assert.equal(main.DB.raw.prepare("SELECT balance FROM billing_spend_wallets WHERE owner='alice'").get().balance,19992000);
   assert.equal(backup.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='ledgeralice'").get().balance,19996000,'central settlement waits for reconnect');
   offline=false;
   r=await call(main,mainOrigin,'/api/billing/status',{},'alice');assert.equal(r.status,200);assert.equal(r.value.wallet.available_vnd,19992);
   const balance=backup.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='ledgeralice'").get().balance;assert.equal(balance,19992000);
   await call(main,mainOrigin,'/api/billing/status',{},'alice');assert.equal(backup.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='ledgeralice'").get().balance,balance,'no double settlement');
   // Authority must never call the model, even with its admin login.
   r=await call(backup,backupOrigin,'/api/provider/model',ai);assert.equal(r.status,503);assert.equal(r.value.code,'PRIMARY_AI_REQUIRED');assert.equal(modelCalls,2);
   // Prove the offline cap stops the provider before a further debit/model call.
   offline=true;
   main.DB.raw.prepare("UPDATE billing_spend_wallets SET balance=1 WHERE owner='alice'").run();
   r=await call(main,mainOrigin,'/api/provider/model',ai,'alice');assert.equal(r.status,402);assert.equal(r.value.code,'TOKEN_BALANCE_LOW');assert.equal(modelCalls,2);
   assert.equal(backup.DB.raw.prepare('SELECT count(*) AS n FROM users WHERE username=?').get('ledgeralice').n,0,'no account/password copied to backup');
   // Restore normal funding in the fixture, then verify unknown usage requires a central admin decision.
   main.DB.raw.prepare("UPDATE billing_spend_wallets SET balance=19992000 WHERE owner='alice'").run();
   offline=false;unknownUsage=true;
   r=await call(main,mainOrigin,'/api/provider/model',ai,'alice');assert.equal(r.status,503);assert.equal(r.value.code,'BILLING_USAGE_PENDING');
   const pending=main.DB.raw.prepare("SELECT * FROM billing_spend_usage WHERE state='pending_review'").get();assert.ok(pending);
   r=await call(main,mainOrigin,'/api/admin/billing/reconcile',{id:pending.id,tokens:500,note:'verified provider usage'});assert.equal(r.status,200,JSON.stringify(r.value));
   await call(main,mainOrigin,'/api/billing/status',{},'alice');
   await call(main,mainOrigin,'/api/billing/status',{},'alice');
   assert.equal(backup.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='ledgeralice'").get().balance,19990000);
   assert.equal(main.DB.raw.prepare("SELECT state FROM billing_spend_usage WHERE id=?").get(pending.id).state,'reconciled');
   // A caller cannot impersonate the trusted source without the link signature.
   const forged=await worker.fetch(new Request(backupOrigin+'/api/internal/billing-central',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'config',source:mainOrigin,created:Date.now(),nonce:crypto.randomUUID()})}),backup,{});assert.equal(forged.status,401);
   const callsBefore=modelCalls;
   main.BILLING_ACCOUNT_MAP=JSON.stringify({alice:'anotherledger'});
   r=await call(main,mainOrigin,'/api/provider/model',ai,'alice');assert.equal(r.status,409);assert.equal(r.value.code,'BILLING_MAPPING_CHANGED');assert.equal(modelCalls,callsBefore);
   main.BILLING_ACCOUNT_MAP=JSON.stringify({alice:'ledgeralice',bob:'ledgeralice'});
   r=await call(main,mainOrigin,'/api/provider/model',ai,'alice');assert.equal(r.status,503);assert.equal(modelCalls,callsBefore,'duplicate owner mapping must not mint spendable money twice');
   main.BILLING_ACCOUNT_MAP=JSON.stringify({alice:'ledgeralice'});
   const setup=await call(main,mainOrigin,'/api/admin/billing/config/get');assert.equal(setup.value.config.webhook_url,backupOrigin+'/api/billing/webhook');
   const topupId=crypto.randomUUID();
   r=await call(main,mainOrigin,'/api/billing/order',{kind:'topup',amount:20000,request_id:topupId},'alice');assert.equal(r.status,200);
   const order=r.value.order;
   const transaction={id:'bank-fixture-transaction',transferType:'in',accountNumber:'0123456789',content:order.memo,transferAmount:20000};
   const webhook=()=>worker.fetch(new Request(mainOrigin+'/api/billing/webhook',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Apikey fixture-webhook-secret-more-than-32'},body:JSON.stringify(transaction)}),main,{});
   offline=true;assert.equal((await webhook()).status,503);
   assert.equal(backup.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='ledgeralice'").get().balance,19990000);
   offline=false;
   assert.equal((await webhook()).status,200);assert.equal((await webhook()).status,200);
   assert.equal(backup.DB.raw.prepare("SELECT balance FROM billing_wallets WHERE owner='ledgeralice'").get().balance,39990000,'one central bank credit across webhook retries');
   assert.equal(backup.DB.raw.prepare('SELECT count(*) AS n FROM billing_receipts WHERE order_id=?').get(order.id).n,1);
  }finally{globalThis.fetch=original;}
 });
}
