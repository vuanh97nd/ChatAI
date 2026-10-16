// Central wallet authority + prepaid spending delegation. Inlined in both Workers.
const centralBillingPath='/api/internal/billing-central';
const centralBillingSchemas=new WeakMap(),spendDatabases=new WeakMap();
function billingTopology(env){
 const role=String(env.BILLING_ROLE||'local');
 if(role==='local')return null;
 if(!['primary','authority'].includes(role))throw new Error('Invalid billing role');
 const peer=new URL(String(role==='primary'?env.BILLING_AUTHORITY_URL:env.BILLING_PRIMARY_URL));
 if(peer.protocol!=='https:'||peer.username||peer.password||peer.search||peer.hash||peer.pathname!=='/')throw new Error('Billing peer must be an HTTPS origin');
 const key=String(env.BILLING_LINK_KEY||'');if(key.length<32)throw new Error('Missing billing link secret');
 return {role,peer:peer.origin,key};
}
async function centralBillingSchema(db){
 if(centralBillingSchemas.has(db))return centralBillingSchemas.get(db);
 const job=db.batch([
  db.prepare('CREATE TABLE IF NOT EXISTS billing_link_nonces(id TEXT PRIMARY KEY,created INTEGER NOT NULL)'),
  db.prepare('CREATE TABLE IF NOT EXISTS billing_allocations(id TEXT PRIMARY KEY,source TEXT NOT NULL,owner TEXT NOT NULL,amount INTEGER NOT NULL,credited INTEGER NOT NULL DEFAULT 0,created INTEGER NOT NULL)'),
  db.prepare('CREATE INDEX IF NOT EXISTS billing_allocations_owner ON billing_allocations(source,owner)'),
  db.prepare('CREATE TABLE IF NOT EXISTS billing_settlements(source TEXT NOT NULL,owner TEXT NOT NULL,spent INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(source,owner))'),
  db.prepare('CREATE TABLE IF NOT EXISTS billing_source_usage(id TEXT PRIMARY KEY,source TEXT NOT NULL,owner TEXT NOT NULL,reserved INTEGER NOT NULL)'),
  db.prepare('CREATE TABLE IF NOT EXISTS billing_decisions(id TEXT PRIMARY KEY,tokens INTEGER NOT NULL,note TEXT NOT NULL,actor TEXT NOT NULL)'),
  db.prepare('CREATE TABLE IF NOT EXISTS billing_spend_state(owner TEXT PRIMARY KEY,granted INTEGER NOT NULL DEFAULT 0,intent TEXT,actor TEXT NOT NULL,synced INTEGER NOT NULL DEFAULT 0,ledger_owner TEXT NOT NULL)'),
  db.prepare('CREATE TABLE IF NOT EXISTS billing_spend_synced(id TEXT PRIMARY KEY,state TEXT NOT NULL,tokens INTEGER,charged INTEGER NOT NULL)'),
  db.prepare('CREATE TABLE IF NOT EXISTS billing_source_cache(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT NOT NULL,updated INTEGER NOT NULL)')
  ,db.prepare('CREATE TABLE IF NOT EXISTS billing_central_imports(id TEXT PRIMARY KEY,source TEXT NOT NULL,fingerprint TEXT NOT NULL,created INTEGER NOT NULL,configured INTEGER NOT NULL DEFAULT 0)')
 ]).catch(error=>{centralBillingSchemas.delete(db);throw error;});
 centralBillingSchemas.set(db,job);return job;
}
function billingSpendDB(db){
 if(spendDatabases.has(db))return spendDatabases.get(db);
 const proxy={prepare(sql){return db.prepare(sql.replace(/\bbilling_(wallets|orders|receipts|usage_prices|usage)\b/g,'billing_spend_$1'));},batch(items){return db.batch(items);}};
 spendDatabases.set(db,proxy);return proxy;
}
function billingPublicActor(actor,name=actor.username){
 return {username:name,role:administrator(actor)?'system':'user',is_system:administrator(actor),created_at:actor.created_at||actor.updated_at||null};
}
function billingMappedActor(env,actor){
 if(administrator(actor))return billingPublicActor(actor,'admin');
 const map=JSON.parse(env.BILLING_ACCOUNT_MAP||'{}');
 if(!map||Array.isArray(map)||typeof map!=='object'||Object.keys(map).length>10000||Object.entries(map).some(([local,remote])=>!validUser(local)||local==='admin'||!validUser(remote)||remote==='admin')||new Set(Object.values(map)).size!==Object.values(map).length)throw new Error('Billing mappings must be explicit and one-to-one');
 const target=map[actor.username];
 if(!validUser(target))throw new Error('Billing account is not explicitly mapped');
 return billingPublicActor(actor,target);
}
async function billingLinkMac(key,text){
 const imported=await crypto.subtle.importKey('raw',new TextEncoder().encode(key),{name:'HMAC',hash:'SHA-256'},false,['sign']);
 return Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',imported,new TextEncoder().encode(text)))).map(n=>n.toString(16).padStart(2,'0')).join('');
}
async function billingCentralCall(env,action,actor,payload={}){
 const cfg=billingTopology(env);if(cfg?.role!=='primary')throw new Error('Not a billing primary');
 let publicURL;
 try{
  publicURL=new URL(String(env.BILLING_PUBLIC_ORIGIN));
  if(publicURL.protocol!=='https:'||publicURL.username||publicURL.password||publicURL.search||publicURL.hash||publicURL.pathname!=='/')throw new Error('Invalid origin');
 }catch{throw Object.assign(new Error('Invalid BILLING_PUBLIC_ORIGIN'),{billingCause:'BILLING_PUBLIC_ORIGIN_INVALID'});}
 const origin=publicURL.origin;
 const envelope={action,actor:actor?billingMappedActor(env,actor):null,payload,source:origin,created:Date.now(),nonce:crypto.randomUUID()};
 const raw=JSON.stringify(envelope),signature=await billingLinkMac(cfg.key,raw);
 const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),action==='import'?45000:8000);
 try{
  // Never follow redirects or forward a user's password/session/API key.
  const response=await fetch(cfg.peer+centralBillingPath,{method:'POST',headers:{'Content-Type':'application/json','X-Billing-Signature':signature},body:raw,redirect:'error',signal:abort.signal});
  const text=await response.text();if(text.length>2000000)throw Object.assign(new Error('Oversized billing response'),{billingCause:'BILLING_RESPONSE_TOO_LARGE'});
  let result;
  try{result=JSON.parse(text);}
  catch{throw Object.assign(new Error('Billing peer did not return JSON'),{billingCause:'BILLING_LINK_NON_JSON_HTTP_'+response.status});}
  return {status:response.status,result};
 }catch(error){
  if(!error.billingCause)error.billingCause=abort.signal.aborted?'BILLING_LINK_TIMEOUT':'BILLING_LINK_NETWORK';
  throw error;
 }finally{clearTimeout(timer);}
}
async function billingRemoteConfig(env){
 if(env.BILLING_CONFIG_OVERRIDE)return env.BILLING_CONFIG_OVERRIDE;
 await centralBillingSchema(env.DB);
 try{
  const {status,result}=await billingCentralCall(env,'config',null);
  if(status!==200||!result.success)throw new Error('Billing config unavailable');
  const config=result.config;
  if(typeof config?.enabled!=='boolean'||!Number.isSafeInteger(config.service_fee)||!Number.isSafeInteger(config.token_price))throw new Error('Invalid billing config');
  await env.DB.prepare('INSERT INTO billing_source_cache VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated=excluded.updated').bind(JSON.stringify(config),Date.now()).run();
  return config;
 }catch{
  const saved=await env.DB.prepare('SELECT data FROM billing_source_cache WHERE id=1').first();
  if(!saved)throw new Error('Billing authority unavailable; no verified configuration');
  return JSON.parse(saved.data);
 }
}
async function billingSyncSpend(env,actor,allocate=true){
 const db=env.DB,spend=billingSpendDB(db);await centralBillingSchema(db);await billingSchema(spend);
 const ledgerActor=billingMappedActor(env,actor);
 await db.prepare('INSERT OR IGNORE INTO billing_spend_state(owner,actor,ledger_owner) VALUES(?,?,?)').bind(actor.username,JSON.stringify(billingPublicActor(actor)),ledgerActor.username).run();
 // Durable intent makes an interrupted allocation response safely repeatable.
 await db.prepare('UPDATE billing_spend_state SET intent=COALESCE(intent,?),actor=? WHERE owner=?').bind(crypto.randomUUID(),JSON.stringify(billingPublicActor(actor)),actor.username).run();
 const local=await db.prepare('SELECT * FROM billing_spend_state WHERE owner=?').bind(actor.username).first();
 if(local.ledger_owner!==ledgerActor.username)throw new Error('Billing mapping changed with outstanding delegated funds');
 const spentRow=await spend.prepare('SELECT COALESCE(SUM(charged),0) AS spent FROM billing_usage WHERE owner=?').bind(actor.username).first();
 const rows=(await spend.prepare(`SELECT u.*,COALESCE(p.price,4000) AS price FROM billing_usage u LEFT JOIN billing_usage_prices p ON p.id=u.id
  LEFT JOIN billing_spend_synced s ON s.id=u.id WHERE u.owner=? AND (s.id IS NULL OR s.state<>u.state OR s.charged<>u.charged OR s.tokens IS NOT u.tokens) ORDER BY u.created,u.id LIMIT 100`).bind(actor.username).all()).results||[];
 const response=await billingCentralCall(env,'sync',actor,{intent:local.intent,seen_granted:local.granted,spent:spentRow.spent,allocate:allocate&&!administrator(actor),rows});
 if(response.status!==200||!response.result.success)throw new Error('Central billing synchronization refused');
 const data=response.result;
 if(!Number.isSafeInteger(data.granted)||data.granted<local.granted)throw new Error('Invalid grant');
 await db.batch([
  spend.prepare('INSERT OR IGNORE INTO billing_wallets(owner,trial_until) VALUES(?,?)').bind(actor.username,data.wallet.trial_until),
  spend.prepare('UPDATE billing_wallets SET balance=balance+?-COALESCE((SELECT granted FROM billing_spend_state WHERE owner=?),0),trial_until=?,service_until=? WHERE owner=? AND ?>=COALESCE((SELECT granted FROM billing_spend_state WHERE owner=?),0)').bind(data.granted,actor.username,data.wallet.trial_until,data.wallet.service_until,actor.username,data.granted,actor.username),
  db.prepare('UPDATE billing_spend_state SET granted=?,intent=CASE WHEN intent=? THEN NULL ELSE intent END,synced=? WHERE owner=? AND granted<=?').bind(data.granted,local.intent,Date.now(),actor.username,data.granted),
  ...rows.map(row=>db.prepare('INSERT INTO billing_spend_synced VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,tokens=excluded.tokens,charged=excluded.charged').bind(row.id,row.state,row.tokens,row.charged))
 ]);
 for(const decision of data.decisions||[]){
  const row=await spend.prepare("SELECT * FROM billing_usage WHERE id=? AND owner=? AND state='pending_review'").bind(decision.id,actor.username).first();
  if(!row)continue;
  const price=await spend.prepare('SELECT price FROM billing_usage_prices WHERE id=?').bind(row.id).first();
  if(Math.ceil(decision.tokens*(price?.price??4000)/1000)>row.reserved)continue;
  await localBillingAPI({...env,DB:spend,BILLING_CONFIG_OVERRIDE:await billingRemoteConfig(env)}, {username:decision.actor,role:'system',is_system:true}, '/api/admin/billing/reconcile',decision,new Request('https://internal/'));
 }
 return data;
}
async function billingCentralAPI(env,request,body,raw){
 const cfg=billingTopology(env);if(cfg?.role!=='authority')return fail('Billing authority not enabled.',404);
 if(request.method!=='POST'||body.source!==cfg.peer||!Number.isSafeInteger(body.created)||Math.abs(Date.now()-body.created)>60000||!/^[-a-f0-9]{36}$/.test(body.nonce||''))return fail('Billing link rejected.',401);
 if(!same(request.headers.get('X-Billing-Signature')||'',await billingLinkMac(cfg.key,raw)))return fail('Billing link authentication failed.',401);
 await centralBillingSchema(env.DB);await billingSchema(env.DB);
 await env.DB.prepare('DELETE FROM billing_link_nonces WHERE created<?').bind(Date.now()-120000).run();
 const used=await env.DB.prepare('INSERT OR IGNORE INTO billing_link_nonces VALUES(?,?)').bind(body.nonce,Date.now()).run();
 if(!used.meta?.changes)return fail('Billing link replay rejected.',409);
 const config=await billingConfig(env);
 if(body.action==='config')return reply({success:true,config:{enabled:config.enabled===true,service_fee:billingServiceFee(config),token_price:billingTokenPrice(config)}});
 const actor=body.actor;
 if(actor&&(!validUser(actor.username)&&actor.username!=='admin'||!['user','system'].includes(actor.role)||actor.is_system!==(actor.role==='system')||(actor.is_system&&actor.username!=='admin')))return fail('Invalid billing identity.',403);
 const payload=body.payload||{};
 if(body.action==='import'){
  if(!administrator(actor))return fail('Admin required.',403);
  return billingImportLedger(env,body.source,payload);
 }
 if(env.BILLING_MIGRATION_FREEZE==='true')return billingError('Đang chuyển sổ thanh toán. Tạm dừng giao dịch.',503,'BILLING_MIGRATION_FREEZE');
 if(body.action==='api'){
  const path=payload.path;
  if(!(typeof path==='string'&&(path.startsWith('/api/billing/')||path.startsWith('/api/admin/billing/'))))return fail('Invalid billing path.');
  if(path!=='/api/billing/webhook'&&!actor)return fail('Billing identity required.',401);
  const identities=payload.identities||{};
  const forwarded=new Request(new URL(path,request.url),{method:'POST',headers:{Authorization:payload.webhook_authorization||''}});
  const response=await billingAPI({...env,BILLING_IDENTITIES:identities},actor,path,payload.body||{},forwarded);
  if(path==='/api/billing/status'&&response.ok){
   const result=await response.json();
   const grant=await env.DB.prepare('SELECT COALESCE(SUM(amount),0) AS granted FROM billing_allocations WHERE source=? AND owner=?').bind(body.source,actor.username).first();
   const settled=await env.DB.prepare('SELECT spent FROM billing_settlements WHERE source=? AND owner=?').bind(body.source,actor.username).first();
   result.delegated_balance_milli=grant.granted-(settled?.spent||0);
   return reply(result,response.status);
  }
  return response;
 }
 if(body.action==='totals'){
  if(!administrator(actor))return fail('Admin required.',403);
  if(!Array.isArray(payload.owners)||payload.owners.length>500||payload.owners.some(n=>!validUser(n)&&n!=='admin'))return fail('Invalid billing owners.');
  return reply({success:true,totals:Object.fromEntries(await adminBillingTotals(env,payload.owners))});
 }
 if(body.action!=='sync'||!actor)return fail('Unknown billing link operation.');
 return billingAuthoritySync(env,body.source,actor,payload);
}
async function billingAuthoritySync(env,source,actor,payload){
 const db=env.DB;
 if(!/^[-a-f0-9]{36}$/.test(payload.intent||'')||!Number.isSafeInteger(payload.seen_granted)||payload.seen_granted<0||!Number.isSafeInteger(payload.spent)||payload.spent<0||!Array.isArray(payload.rows)||payload.rows.length>100)return fail('Invalid spend synchronization.');
 const wallet=await billingWallet(env,actor);
 const existing=await db.prepare('SELECT * FROM billing_allocations WHERE id=?').bind(payload.intent).first();
 if(existing&&(existing.source!==source||existing.owner!==actor.username))return fail('Allocation identity conflict.',409);
 const total=await db.prepare('SELECT COALESCE(SUM(amount),0) AS granted FROM billing_allocations WHERE source=? AND owner=?').bind(source,actor.username).first();
 const prior=await db.prepare('SELECT spent FROM billing_settlements WHERE source=? AND owner=?').bind(source,actor.username).first();
 if(payload.spent>total.granted||payload.spent<(prior?.spent||0))return fail('Spend exceeds allocated funds or stale settlement.',409);
 for(const row of payload.rows){
  if(!/^[-a-f0-9]{36}$/.test(row.id||'')||!Number.isSafeInteger(row.charged)||row.charged<0||!Number.isSafeInteger(row.reserved)||row.reserved<0||!Number.isSafeInteger(row.created)||row.created<0||!Number.isSafeInteger(row.price)||row.price<1||row.price>10000000||!(row.tokens===null||Number.isSafeInteger(row.tokens)&&row.tokens>=0)||!['reserved','charged','released','pending_review','reconciled','free','free_unknown_usage'].includes(row.state))return fail('Invalid usage ledger row.');
  if(['charged','reconciled'].includes(row.state)&&row.charged!==Math.ceil(row.tokens*row.price/1000)||!['charged','reconciled'].includes(row.state)&&row.charged!==0)return fail('Invalid usage charge.');
  const collision=await db.prepare('SELECT source,owner FROM billing_source_usage WHERE id=?').bind(row.id).first();
  const old=await db.prepare('SELECT owner FROM billing_usage WHERE id=?').bind(row.id).first();
  if(collision&&(collision.source!==source||collision.owner!==actor.username)||old&&!collision)return fail('Usage ID conflict.',409);
 }
 await db.batch([
  db.prepare('INSERT OR IGNORE INTO billing_settlements(source,owner) VALUES(?,?)').bind(source,actor.username),
  db.prepare('UPDATE billing_wallets SET balance=balance+COALESCE((SELECT spent FROM billing_settlements WHERE source=? AND owner=?),0)-?,held=held+COALESCE((SELECT spent FROM billing_settlements WHERE source=? AND owner=?),0)-? WHERE owner=? AND COALESCE((SELECT spent FROM billing_settlements WHERE source=? AND owner=?),0)<=?').bind(source,actor.username,payload.spent,source,actor.username,payload.spent,actor.username,source,actor.username,payload.spent),
  db.prepare('UPDATE billing_settlements SET spent=max(spent,?) WHERE source=? AND owner=?').bind(payload.spent,source,actor.username),
  db.prepare(`INSERT OR IGNORE INTO billing_allocations(id,source,owner,amount,created)
   SELECT ?,?,?,max(0,balance-held),? FROM billing_wallets WHERE owner=? AND ?=1 AND ?=(SELECT COALESCE(SUM(amount),0) FROM billing_allocations WHERE source=? AND owner=?)`).bind(payload.intent,source,actor.username,Date.now(),actor.username,payload.allocate===true?1:0,payload.seen_granted,source,actor.username),
  db.prepare('UPDATE billing_wallets SET held=held+COALESCE((SELECT amount FROM billing_allocations WHERE id=? AND credited=0),0) WHERE owner=?').bind(payload.intent,actor.username),
  db.prepare('UPDATE billing_allocations SET credited=1 WHERE id=?').bind(payload.intent),
  ...payload.rows.flatMap(row=>[
   db.prepare('INSERT OR IGNORE INTO billing_source_usage VALUES(?,?,?,?)').bind(row.id,source,actor.username,row.reserved),
   db.prepare('INSERT INTO billing_usage(id,owner,reserved,tokens,charged,state,created) VALUES(?,?,0,?,?,?,?) ON CONFLICT(id) DO UPDATE SET tokens=excluded.tokens,charged=excluded.charged,state=excluded.state').bind(row.id,actor.username,row.tokens,row.charged,['pending_review','reserved'].includes(row.state)?'delegated_'+row.state:row.state,row.created),
   db.prepare('INSERT INTO billing_usage_prices VALUES(?,?) ON CONFLICT(id) DO UPDATE SET price=excluded.price').bind(row.id,row.price)
  ])
 ]);
 const granted=await db.prepare('SELECT COALESCE(SUM(amount),0) AS granted FROM billing_allocations WHERE source=? AND owner=?').bind(source,actor.username).first();
 const decisions=await db.prepare('SELECT d.* FROM billing_decisions d JOIN billing_source_usage u ON u.id=d.id WHERE u.source=? AND u.owner=?').bind(source,actor.username).all();
 return reply({success:true,granted:granted.granted,wallet:await billingWallet(env,actor),decisions:decisions.results||[]});
}
async function billingSourceAPI(env,actor,path,body,request){
 try{
  if(actor)await billingSyncSpend(env,actor,false);
  const clean={...body};delete clean.username;delete clean.key;
  const identities={};
  if(clean.target){
   if(!administrator(actor))return fail('Admin required.',403);
   const user=await env.DB.prepare('SELECT * FROM users WHERE username=?').bind(clean.target).first();
   if(!user||user.account_status==='deleted')return fail('Không tìm thấy tài khoản.',404);
   await billingSyncSpend(env,user,false);
   const mapped=billingMappedActor(env,user);identities[mapped.username]=mapped;clean.target=mapped.username;
  }
  const {status,result}=await billingCentralCall(env,'api',actor,{path,body:clean,identities,webhook_authorization:path==='/api/billing/webhook'?request.headers.get('Authorization'):undefined});
  if(path==='/api/billing/status'&&status===200&&result.wallet){
   const local=await billingSpendDB(env.DB).prepare('SELECT balance,held FROM billing_wallets WHERE owner=?').bind(actor.username).first();
   if(local&&Number.isSafeInteger(result.delegated_balance_milli)){
    const w=result.wallet,delegated=result.delegated_balance_milli;
    w.balance=w.balance-delegated+local.balance;w.held=w.held-delegated+local.held;
    w.balance_vnd=w.balance/1000;w.held_vnd=w.held/1000;w.available_vnd=(w.balance-w.held)/1000;
   }
   result.billing_server=billingTopology(env).peer;result.topups_available=true;
  }
  return reply(result,status);
 }catch{
  if(path==='/api/billing/status'&&actor){
   const db=billingSpendDB(env.DB);await billingSchema(db);
   const verified=await db.prepare('SELECT owner FROM billing_wallets WHERE owner=?').bind(actor.username).first();
   if(verified){
    const response=await localBillingAPI({...env,DB:db,BILLING_CONFIG_OVERRIDE:{...(await billingRemoteConfig(env)),enabled:false}},actor,path,body,request);
    const data=await response.json();data.billing_offline=true;data.topups_available=false;
    data.message='Server thanh toán tạm ngừng. Chỉ dùng số tiền đã được xác nhận còn lại; không nạp tiền hoặc tạo QR.';
    return reply(data);
   }
  }
  return reply({success:false,code:'BILLING_AUTHORITY_UNAVAILABLE',message:'Server thanh toán dự phòng không khả dụng. Tạm khóa nạp tiền, tạo QR và thay đổi số dư; không tự chuyển sang ví khác.'},503);
 }
}
async function billingDelegatedProvider(env,actor,path,body){
 if(env.BILLING_MIGRATION_FREEZE==='true')return billingError('Đang chuyển sổ thanh toán; tạm dừng yêu cầu AI.',503,'BILLING_MIGRATION_FREEZE');
 let config;
 try{
  const mapped=billingMappedActor(env,actor);await centralBillingSchema(env.DB);
  const existing=await env.DB.prepare('SELECT ledger_owner FROM billing_spend_state WHERE owner=?').bind(actor.username).first();
  if(existing&&existing.ledger_owner!==mapped.username)return billingError('Ánh xạ chủ ví đã đổi; cần đối soát tiền đã cấp trước khi đổi ví.',409,'BILLING_MAPPING_CHANGED');
  config=await billingRemoteConfig(env);
 }
 catch{return billingError('Chưa có cấu hình hoặc ghép tài khoản thanh toán đã xác minh.',503,'BILLING_NOT_READY');}
 const db=billingSpendDB(env.DB);await billingSchema(db);
 try{await billingSyncSpend(env,actor,config.enabled===true);}catch{
  const verified=await db.prepare('SELECT owner FROM billing_wallets WHERE owner=?').bind(actor.username).first();
  if(!verified&&!administrator(actor))return billingError('Server thanh toán lỗi; chưa có tiền đã xác nhận để sử dụng.',503,'BILLING_NOT_READY');
 }
 const delegated={...env,DB:db,BILLING_CONFIG_OVERRIDE:config};
 // Reuse the established atomic reservation/usage billing logic on delegated money only.
 const response=await localBillingProvider(delegated,actor,path,body);
 if(response.headers.get('Content-Type')?.includes('text/event-stream'))return response;
 try{await billingSyncSpend(env,actor,false);}catch{/* Durable local charge remains; never retry model or invent credit. */}
 return response;
}
async function billingAPI(env,actor,path,body,request){
 if(path==='/api/admin/billing/central-check')return billingCentralCheck(env,actor);
 const topology=billingTopology(env);
 if(topology?.role==='primary'&&path==='/api/admin/billing/central-migration')return billingMigrateLedger(env,actor,body);
 if(topology&&env.BILLING_MIGRATION_FREEZE==='true')return billingError('Đang chuyển sổ thanh toán. Tạm dừng giao dịch.',503,'BILLING_MIGRATION_FREEZE');
 if(topology?.role==='primary')return billingSourceAPI(env,actor,path,body,request);
 if(topology?.role==='authority'&&path==='/api/admin/billing/reconcile'){
  if(!administrator(actor))return fail('Admin required.',403);
  await centralBillingSchema(env.DB);
  const source=await env.DB.prepare('SELECT * FROM billing_source_usage WHERE id=?').bind(body.id||'').first();
  if(source){
   if(!Number.isSafeInteger(body.tokens)||body.tokens<0||typeof body.note!=='string'||!body.note.trim()||body.note.length>300)return fail('Invalid reconciliation.');
   const row=await env.DB.prepare('SELECT state FROM billing_usage WHERE id=?').bind(body.id).first();
   if(row?.state!=='delegated_pending_review')return fail('Lượt không chờ đối soát.',409);
   const price=await env.DB.prepare('SELECT price FROM billing_usage_prices WHERE id=?').bind(body.id).first();
   if(Math.ceil(body.tokens*(price?.price??4000)/1000)>source.reserved)return fail('Số token vượt hạn mức đã giữ; cần kiểm tra sổ trước khi đối soát.',409);
   const old=await env.DB.prepare('SELECT * FROM billing_decisions WHERE id=?').bind(body.id).first();
   if(old&&(old.tokens!==body.tokens||old.note!==body.note.trim()))return fail('Đã có quyết định đối soát khác.',409);
   await env.DB.prepare('INSERT OR IGNORE INTO billing_decisions VALUES(?,?,?,?)').bind(body.id,body.tokens,body.note.trim(),actor.username).run();
   return reply({success:true,message:'Đã lưu quyết định đối soát. Số dư sẽ cập nhật sau khi server chính xác nhận; chưa trừ tiền lần nữa.'});
  }
 }
 return localBillingAPI(env,actor,path,body,request);
}
const billingMigrationColumns={
 billing_wallets:['owner','balance','held','trial_until','service_until'],
 billing_orders:['id','owner','kind','amount','memo','status','created','expires'],
 billing_receipts:['id','order_id','actor','credited','created','note'],
 billing_usage:['id','owner','reserved','tokens','charged','state','created'],
 billing_usage_prices:['id','price']
};
async function billingMigrateLedger(env,actor,body){
 if(!administrator(actor))return fail('Admin required.',403);
 if(env.BILLING_MIGRATION_FREEZE!=='true'||body.confirm!=='MIGRATE_BILLING_TO_BACKUP'||!/^[-a-f0-9]{36}$/.test(body.request_id||''))return fail('Freeze billing and supply explicit migration confirmation plus a UUID.',409);
 await billingSchema(env.DB);
 const tables={};
 for(const [table,columns] of Object.entries(billingMigrationColumns)){
  const rows=(await env.DB.prepare('SELECT '+columns.join(',')+' FROM '+table).all()).results||[];
  if(rows.length>10000)return fail('Ledger too large for one atomic import; use a reviewed database migration.',409);
  tables[table]=rows.map(row=>row.owner?{...row,owner:row.owner==='admin'?'admin':billingMappedActor(env,{username:row.owner}).username}:row);
 }
 const rawConfig=await billingConfig({...env,BILLING_ROLE:'local'});
 const config={enabled:rawConfig.enabled===true,bank:rawConfig.bank||'',account:rawConfig.account||'',name:rawConfig.name||'',secret:rawConfig.secret||'',service_fee:billingServiceFee(rawConfig),token_price:billingTokenPrice(rawConfig)};
 try{
  const {status,result}=await billingCentralCall(env,'import',actor,{id:body.request_id,tables,config});
  return reply(result,status);
 }catch(error){
  const cause=error.billingCause||'BILLING_LINK_CONFIG_OR_REQUEST';
  const reference=crypto.randomUUID();console.error('billing_migration_unconfirmed',reference,cause);
  return reply({success:false,code:'BILLING_MIGRATION_UNCONFIRMED',cause,reference,message:'Chưa xác nhận chuyển sổ. Nguyên nhân: '+cause+'. Giữ freeze và request_id cũ; không xóa dữ liệu nguồn.'},503);
 }
}
async function billingCentralCheck(env,actor){
 if(!administrator(actor))return fail('Admin required.',403);
 const checks={role:env.BILLING_ROLE||'local',freeze:env.BILLING_MIGRATION_FREEZE==='true',
  authority_url_set:Boolean(env.BILLING_AUTHORITY_URL),public_origin_set:Boolean(env.BILLING_PUBLIC_ORIGIN),
  link_key_present:typeof env.BILLING_LINK_KEY==='string'&&env.BILLING_LINK_KEY.length>=32};
 try{
  const cfg=billingTopology(env);checks.authority_url_valid=cfg?.role==='primary';
  if(cfg?.role!=='primary')return reply({success:true,connected:false,checks,cause:'BILLING_PRIMARY_ROLE_MISSING'});
  const {status,result}=await billingCentralCall(env,'config',null);
  const connected=status===200&&result.success===true&&typeof result.config?.enabled==='boolean';
  let cause=null;
  if(!connected)cause=status===401?'BILLING_LINK_AUTH_OR_ORIGIN_MISMATCH':status===404?'BACKUP_AUTHORITY_ROLE_OR_CODE_MISSING':'BILLING_PEER_HTTP_'+status;
  return reply({success:true,connected,checks,peer_http_status:status,cause});
 }catch(error){return reply({success:true,connected:false,checks,cause:error.billingCause||'BILLING_LINK_CONFIGURATION_INVALID'});}
}
async function billingImportLedger(env,source,payload){
 if(env.BILLING_MIGRATION_FREEZE!=='true')return fail('Authority must be frozen before importing ledger.',409);
 if(!/^[-a-f0-9]{36}$/.test(payload.id||'')||!payload.tables||typeof payload.config!=='object')return fail('Invalid migration snapshot.');
 const fingerprint=await tokenDigest(JSON.stringify(payload));
 const existing=await env.DB.prepare('SELECT * FROM billing_central_imports WHERE id=?').bind(payload.id).first();
 if(existing){
  if(existing.source!==source||existing.fingerprint!==fingerprint)return fail('Migration ID conflict.',409);
  // Re-apply only the encrypted configuration if a previous response was interrupted.
  if(!existing.configured)await billingImportConfig(env,payload.config,payload.id);
  return reply({success:true,already_imported:true,message:'Sổ đã chuyển trước đó; không cộng tiền lần nữa.'});
 }
 const statements=[];
 for(const [table,columns] of Object.entries(billingMigrationColumns)){
  const rows=payload.tables[table];
  if(!Array.isArray(rows)||rows.length>10000)return fail('Invalid migration table.');
  for(const row of rows){
   if(Object.keys(row).length!==columns.length||columns.some(k=>!Object.hasOwn(row,k)))return fail('Invalid migration columns.');
   for(const [key,value] of Object.entries(row)){
    if(typeof value==='number'&&(!Number.isSafeInteger(value)||value<0)||typeof value==='string'&&value.length>2000||!(value===null||typeof value==='number'||typeof value==='string'))return fail('Invalid ledger value.');
   }
   if(row.owner&&!validUser(row.owner)&&row.owner!=='admin')return fail('Invalid ledger owner.');
   statements.push(env.DB.prepare('INSERT INTO '+table+'('+columns.join(',')+') VALUES('+columns.map(()=>'?').join(',')+')').bind(...columns.map(k=>row[k])));
  }
  const count=await env.DB.prepare('SELECT count(*) AS n FROM '+table).first();
  if(count.n)return fail('Ví đích đã có dữ liệu. Không ghi đè hoặc cộng gộp tự động; cần đối chiếu hai sổ trước.',409);
 }
 const allocated=await env.DB.prepare('SELECT count(*) AS n FROM billing_allocations').first();
 if(allocated.n)return fail('Spending has already been delegated; cannot import ledger.',409);
 const config=payload.config;
 if(typeof config.enabled!=='boolean'||!Number.isSafeInteger(config.service_fee)||!Number.isSafeInteger(config.token_price)||typeof config.secret!=='string'||typeof config.bank!=='string'||typeof config.account!=='string'||typeof config.name!=='string')return fail('Invalid payment configuration.');
 // Schema and secret wrapping are prepared before committing any balances.
 const current=await billingConfig(env);
 if(current.secret||current.bank||current.account)return fail('Đích đã có cấu hình ngân hàng. Không ghi đè; cần đối chiếu cấu hình trước.',409);
 await env.DB.batch([...statements,env.DB.prepare('INSERT INTO billing_central_imports(id,source,fingerprint,created) VALUES(?,?,?,?)').bind(payload.id,source,fingerprint,Date.now())]);
 await billingImportConfig(env,config,payload.id);
 return reply({success:true,counts:Object.fromEntries(Object.entries(payload.tables).map(([name,rows])=>[name,rows.length])),message:'Đã chuyển sổ và cấu hình thanh toán. Nguồn được giữ nguyên để kiểm tra, không còn là ví hoạt động sau khi bỏ freeze.'});
}
async function billingImportConfig(env,config,id){
 await writeProviderConfig(env,'billing_sepay',{key:config.secret,model:JSON.stringify({...config,secret:undefined})});
 await env.DB.prepare('UPDATE billing_central_imports SET configured=1 WHERE id=?').bind(id).run();
}
async function billingProvider(env,actor,path,body){
 if(path!=='/api/provider/model')return providerAPI(env,path,body);
 const topology=billingTopology(env);
 if(topology?.role==='primary'&&path==='/api/provider/model')return billingDelegatedProvider(env,actor,path,body);
 if(topology?.role==='authority'&&path==='/api/provider/model')return billingError('AI chạy trên server chính; server này chỉ quản lý thanh toán.',503,'PRIMARY_AI_REQUIRED');
 return localBillingProvider(env,actor,path,body);
}
async function billingScheduledSync(env){
 if(billingTopology(env)?.role!=='primary')return;
 await centralBillingSchema(env.DB);
 const rows=await env.DB.prepare('SELECT owner,actor FROM billing_spend_state ORDER BY synced,owner LIMIT 100').all();
 for(const row of rows.results||[]){
  try{await billingSyncSpend(env,JSON.parse(row.actor),false);}
  catch{await env.DB.prepare('UPDATE billing_spend_state SET synced=? WHERE owner=?').bind(Date.now(),row.owner).run();break;}
 }
}
async function adminBillingTotals(env,owners,now=Date.now()){
 if(billingTopology(env)?.role!=='primary')return localAdminBillingTotals(env,owners,now);
 const map=new Map();
 try{
  const mapped=owners.map(username=>[username,username==='admin'?'admin':billingMappedActor(env,{username}).username]);
  const {status,result}=await billingCentralCall(env,'totals',{username:'admin',role:'system',is_system:true},{owners:mapped.map(pair=>pair[1])});
  if(status!==200||!result.success)throw new Error('Billing totals unavailable');
  for(const [local,remote] of mapped)map.set(local,result.totals[remote]);
  return map;
 }catch{
  let config;
  try{config=await billingRemoteConfig(env);}catch{return new Map(owners.map(owner=>[owner,{billing_unavailable:true,billing_offline:true}]))}
  await billingSchema(billingSpendDB(env.DB));
  const values=await localAdminBillingTotals({...env,DB:billingSpendDB(env.DB),BILLING_CONFIG_OVERRIDE:config},owners,now);
  for(const [owner,value] of values)map.set(owner,{...value,billing_offline:true,counting_scope:'Verified delegated funds and local usage; authority unavailable'});
  return map;
 }
}
