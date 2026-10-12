import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import dashboard from '../../work.js';
import server from '../worker.js';
function environment(){
 const raw=new DatabaseSync(':memory:');
 const DB={raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){return Promise.all(items.map(item=>item.run()));}};
 return {DB,ADMIN_KEY:'test-admin-key-with-enough-length'};
}
async function call(worker,env,path,body){
 const response=await worker.fetch(new Request('https://example.org'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'admin',key:env.ADMIN_KEY,...body})}),env,{});
 const value=await response.json();assert.equal(response.status,200,JSON.stringify(value));return value;
}
for(const [name,worker] of [['dashboard',dashboard],['worker',server]]){
 test(`${name}: OpenRouter settings are encrypted and scoped to each server; catalog and generation use saved model`,async()=>{
  const main=environment(),backup=environment(),oldFetch=globalThis.fetch,seen=[];
  try{
   for(const [env,key,model] of [[main,'main-openrouter-secret','openai/gpt-4.1-mini'],[backup,'backup-openrouter-secret','vendor/model:free']]){
    await call(worker,env,'/api/admin/providers/save',{providers:{openrouter:key},models:{openrouter:model}});
    const encrypted=env.DB.raw.prepare("SELECT encrypted_value FROM provider_credentials WHERE provider='openrouter'").get().encrypted_value;
    assert.ok(!encrypted.includes(key));
    const status=await call(worker,env,'/api/admin/providers/status',{});
    assert.equal(status.providers.openrouter.model,model);assert.equal(status.providers.openrouter.configured,true);assert.ok(!JSON.stringify(status).includes(key));
   }
   globalThis.fetch=async(url,options)=>{
    seen.push({url,headers:options.headers,payload:options.body?JSON.parse(options.body):null});
    if(url.endsWith('/models'))return Response.json({data:[{id:'vendor/model:free'},{id:'openai/gpt-4.1-mini'}]});
    return Response.json({choices:[{message:{content:'OK'}}]});
   };
   const catalog=await call(worker,backup,'/api/admin/providers/models',{provider:'openrouter'});
   assert.ok(catalog.models.includes('vendor/model:free'));
   assert.equal(seen.at(-1).url,'https://openrouter.ai/api/v1/models');assert.equal(seen.at(-1).headers.Authorization,'Bearer backup-openrouter-secret');
   await call(worker,backup,'/api/provider/model',{provider:'openrouter',format:{type:'object'},messages:[{role:'user',content:'Plan'}]});
   assert.equal(seen.at(-1).url,'https://openrouter.ai/api/v1/chat/completions');assert.equal(seen.at(-1).payload.model,'vendor/model:free');assert.equal(seen.at(-1).payload.response_format.type,'json_object');
   await call(worker,main,'/api/provider/model',{provider:'openrouter',messages:[{role:'user',content:'Hello'}]});
   assert.equal(seen.at(-1).headers.Authorization,'Bearer main-openrouter-secret');assert.equal(seen.at(-1).payload.model,'openai/gpt-4.1-mini');
   const custom=await call(worker,main,'/api/admin/providers/add',{provider:'openrouter',label:'Router model',model:'vendor/model:free'});
   await call(worker,main,'/api/provider/model',{provider:custom.entry.id,messages:[{role:'user',content:'Hello'}]});
   assert.equal(seen.at(-1).headers.Authorization,'Bearer main-openrouter-secret');assert.equal(seen.at(-1).payload.model,'vendor/model:free');
  }finally{globalThis.fetch=oldFetch;main.DB.raw.close();backup.DB.raw.close();}
 });
}
