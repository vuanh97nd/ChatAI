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
 test(`${name}: admin email secrets, verified aliases and single-use password resets`,async()=>{
  const env={DB:database(),ADMIN_KEY:'fixture-admin-secret-32-characters'},original=globalThis.fetch;
  const mail=[],key='re_fixture-secret-never-returned';
  const call=async(path,body={},user='admin',password='fixture-password')=>{
   const r=await worker.fetch(new Request('https://example.org'+path,{method:'POST',headers:{'Content-Type':'application/json','CF-Connecting-IP':'192.0.2.10'},body:JSON.stringify({...body,...(user?{username:user,key:user==='admin'?env.ADMIN_KEY:password}:{})})}),env,{});
   return {status:r.status,data:await r.json()};
  };
  try{
   let r=await call('/api/admin/email/config/get');assert.equal(r.status,200);assert.equal(r.data.config.secret_configured,false);
   env.DB.raw.prepare("INSERT INTO users(username,key,fullname,email,tier,expires_at) VALUES('alice','fixture-password','Alice','alice@example.org','pro','Vĩnh viễn')").run();
   assert.equal((await call('/api/admin/email/config/save',{config:{enabled:true,from:'sender@example.org',name:'ChatAI',secret:key}},'alice')).status,403);
   assert.equal((await call('/api/admin/email/config/save',{config:{enabled:true,from:'sender@example.org',name:'ChatAI',secret:key}})).status,200);
   r=await call('/api/admin/email/config/get');assert.equal(r.data.config.secret_configured,true);assert.ok(!JSON.stringify(r.data).includes(key));
   assert.ok(!env.DB.raw.prepare("SELECT encrypted_value FROM provider_credentials WHERE provider='email_resend'").get().encrypted_value.includes(key));
   globalThis.fetch=async(url,options)=>{assert.equal(url,'https://api.resend.com/emails');assert.equal(options.headers.Authorization,'Bearer '+key);mail.push(JSON.parse(options.body));return Response.json({id:'mail-'+mail.length});};
   await call('/api/admin/email/config/save',{config:{enabled:true,from:'sender@example.org',name:'ChatAI',secret:''}});
   assert.equal((await call('/api/admin/email/test',{to:'test@example.org'})).status,200);
   assert.equal((await call('/api/admin/email/test',{to:'test@example.org'},'alice')).status,403);
   assert.equal((await call('/api/login',{device_id:'test'},'ALICE@example.org')).status,401);
   assert.equal((await call('/api/email/verification/request',{},'alice')).status,200);
   const link=mail.at(-1).text.match(/https:\/\/[^\s]+/)[0],token=new URLSearchParams(new URL(link).hash.slice(1)).get('token');
   assert.equal(mail.at(-1).to[0],'alice@example.org');assert.ok(!JSON.stringify(env.DB.raw.prepare('SELECT * FROM email_actions').all()).includes(token));
   assert.equal((await call('/api/email/verify',{token},null)).status,200);
   assert.equal((await call('/api/email/verify',{token},null)).status,400);
   r=await call('/api/login',{device_id:'test'},'ALICE@example.org');assert.equal(r.status,200);assert.equal(r.data.user.username,'alice');const session=r.data.session_token;
   r=await call('/api/account/profile/get',{},'alice',session);assert.equal(r.data.profile.username,'alice');
   const before=mail.length;
   const unknown=await call('/api/email/password/request',{email:'missing@example.org'},null);assert.equal(unknown.status,200);assert.equal(mail.length,before);
   const known=await call('/api/email/password/request',{email:'alice@example.org'},null);assert.equal(known.status,200);assert.equal(known.data.message,unknown.data.message);
   const resetToken=new URLSearchParams(new URL(mail.at(-1).text.match(/https:\/\/[^\s]+/)[0]).hash.slice(1)).get('token');
   assert.equal((await call('/api/email/verify',{token:resetToken},null)).status,400);
   assert.equal((await call('/api/email/password/reset',{token:resetToken,password:'short'},null)).status,400);
   assert.equal((await call('/api/email/password/reset',{token:resetToken,password:'new-password-strong'},null)).status,200);
   assert.equal((await call('/api/email/password/reset',{token:resetToken,password:'different-password'},null)).status,400);
   assert.equal((await call('/api/account/profile/get',{},'alice',session)).status,401);
   assert.equal((await call('/api/login',{device_id:'test'},'alice','fixture-password')).status,401);
   r=await call('/api/login',{device_id:'test'},'alice@example.org','new-password-strong');assert.equal(r.status,200);assert.equal(r.data.user.username,'alice');
   assert.equal((await call('/api/register',{username:'other',password:'fixture-password',fullname:'Other',email:'ALICE@example.org'},null)).status,409);
   assert.equal((await call('/api/account/profile/update',{profile:{fullname:'Alice',email:'new-alice@example.org'}},'alice',r.data.session_token)).status,200);
   assert.equal((await call('/api/login',{device_id:'test'},'alice@example.org','new-password-strong')).status,401);
   assert.equal((await call('/api/login',{device_id:'test'},'new-alice@example.org','new-password-strong')).status,401);
   assert.equal((await call('/api/login',{device_id:'test'},'alice','new-password-strong')).status,200);
   assert.equal(env.DB.raw.prepare("SELECT COUNT(*) AS n FROM email_identities WHERE owner='alice'").get().n,0);
   const page=await worker.fetch(new Request('https://example.org/email/reset'),env,{});assert.equal(page.status,200);assert.match(page.headers.get('Content-Security-Policy'),/frame-ancestors 'none'/);assert.match(await page.text(),/history.replaceState/);
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });
 test(`${name}: expired verification, duplicate email and provider failures stay closed`,async()=>{
  const env={DB:database(),ADMIN_KEY:'fixture-admin-secret-32-characters'},original=globalThis.fetch;let message;
  const call=async(path,body={},user='admin')=>{
   const r=await worker.fetch(new Request('https://example.org'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,...(user?{username:user,key:user==='admin'?env.ADMIN_KEY:'fixture-password'}:{})})}),env,{});return {status:r.status,data:await r.json()};
  };
  try{
   await call('/api/admin/email/config/save',{config:{enabled:true,from:'sender@example.org',name:'ChatAI',secret:'re_fixture-key'}});
   env.DB.raw.prepare("INSERT INTO users(username,key,email,tier,expires_at) VALUES('bob','fixture-password','bob@example.org','pro','Vĩnh viễn')").run();
   globalThis.fetch=async(url,options)=>{message=JSON.parse(options.body);return Response.json({id:'test'});};
   assert.equal((await call('/api/email/verification/request',{},'bob')).status,200);
   const token=new URLSearchParams(new URL(message.text.match(/https:\/\/[^\s]+/)[0]).hash.slice(1)).get('token');
   env.DB.raw.prepare('UPDATE email_actions SET expires=0').run();
   assert.equal((await call('/api/email/verify',{token},null)).status,400);
   assert.equal((await call('/api/login',{},'bob@example.org')).status,401);
   env.DB.raw.prepare("INSERT INTO users(username,key,email,tier,expires_at) VALUES('duplicate','fixture-password','bob@example.org','pro','Vĩnh viễn')").run();
   assert.equal((await call('/api/email/verification/request',{},'duplicate')).status,409);
   globalThis.fetch=async()=>new Response('provider failure',{status:403});
   const failed=await call('/api/admin/email/test',{to:'receiver@example.org'});assert.equal(failed.status,502);assert.ok(!JSON.stringify(failed.data).includes('re_fixture-key'));
   await call('/api/admin/email/config/save',{config:{enabled:false,from:'sender@example.org',name:'ChatAI',secret:''}});
   assert.equal((await call('/api/email/password/request',{email:'bob@example.org'},null)).status,503);
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });
}
