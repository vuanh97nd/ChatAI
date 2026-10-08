import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import dashboard from '../../work.js';
import server from '../worker.js';
function database(){
 const raw=new DatabaseSync(':memory:');
 return {raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){return Promise.all(items.map(item=>item.run()));}};
}
for(const [name,worker] of [['Dashboard work.js',dashboard],['server worker.js',server]]){
 test(`${name}: JSON planning disables thinking and accepts a larger retry budget`,async()=>{
  const env={DB:database(),ADMIN_KEY:'test-admin-key-with-enough-length',DEEPSEEK_API_KEY:'test-only-key'};
  const original=globalThis.fetch;let payload;
  try{
   globalThis.fetch=async(url,options)=>{payload=JSON.parse(options.body);return Response.json({choices:[{message:{content:'{"answer":"OK","tool":"","arguments":"{}"}'}}]});};
   const response=await worker.fetch(new Request('https://example.org/api/provider/model',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'admin',key:env.ADMIN_KEY,provider:'deepseek_pro',format:{type:'object'},max_tokens:8192,messages:[{role:'user',content:'Lập kế hoạch JSON'}]})}),env,{});
   assert.equal(response.status,200);
   assert.equal(payload.thinking.type,'disabled');assert.equal(payload.max_tokens,8192);
   assert.equal(payload.response_format.type,'json_object');
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });
 for(const source of ['D1','secret'])test(`${name}: three custom DeepSeek entries inherit one ${source} key`,async()=>{
  const env={DB:database(),ADMIN_KEY:'test-admin-key-with-enough-length'};
  const shared='test-shared-deepseek-key';
  const call=async(path,body)=>{
   const response=await worker.fetch(new Request('https://example.workers.dev'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'admin',key:env.ADMIN_KEY,...body})}),env,{});
   const value=await response.json();assert.equal(response.status,200,JSON.stringify(value));return value;
  };
  const original=globalThis.fetch,seen=[],thinking=[];
  try{
   globalThis.fetch=async(url,options)=>{assert.equal(url,'https://api.deepseek.com/chat/completions');assert.equal(options.headers.Authorization,'Bearer '+shared);seen.push(JSON.parse(options.body).model);thinking.push(JSON.parse(options.body).thinking?.type);return Response.json({choices:[{message:{content:'OK'}}]});};
   if(source==='secret')env.DEEPSEEK_API_KEY=shared;
   else await call('/api/admin/providers/save',{providers:{deepseek:shared},models:{deepseek:'deepseek-flash'}});
   for(const provider of ['deepseek_flash','deepseek_pro','deepseek_r1'])await call('/api/provider/model',{provider,messages:[{role:'user',content:'Xin chào'}]});
   assert.deepEqual(seen,['deepseek-flash','deepseek-v4-pro','deepseek-flash']);
   assert.deepEqual(thinking,['disabled','enabled','enabled']);
   seen.length=0;thinking.length=0;
   const models=['deepseek-flash','deepseek-v4-pro','deepseek-reasoner'];
   for(const [index,model] of models.entries()){
    const added=await call('/api/admin/providers/add',{provider:'deepseek',label:'Test DeepSeek '+index,model,api_key:''});
    const answer=await call('/api/provider/model',{provider:added.entry.id,messages:[{role:'user',content:'Xin chào'}]});assert.equal(answer.answer,'OK');
   }
   assert.deepEqual(seen,models);
   const first=await call('/api/admin/providers/deepseek-presets',{});
   const second=await call('/api/admin/providers/deepseek-presets',{});
   assert.deepEqual(first.entries.map(e=>e.id),second.entries.map(e=>e.id));
   assert.deepEqual(first.entries.map(e=>e.model),['deepseek-flash','deepseek-v4-pro','deepseek-flash']);
   assert.deepEqual(first.entries.map(e=>e.thinking_enabled),[false,true,true]);
   assert.ok(!JSON.stringify(first).includes(shared));
   for(const entry of first.entries)await call('/api/provider/model',{provider:entry.id,messages:[{role:'user',content:'Xin chào'}]});
   assert.deepEqual(thinking.slice(-3),['disabled','enabled','enabled']);
   globalThis.fetch=async(url,options)=>{
    const payload=JSON.parse(options.body);assert.equal(payload.stream,true);assert.equal(payload.thinking.type,'disabled');
    return new Response(new ReadableStream({start(c){c.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":"Xin chào"}}]}\n\n'));}}),{headers:{'Content-Type':'text/event-stream'}});
   };
   const streamed=await worker.fetch(new Request('https://example.workers.dev/api/provider/model',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'admin',key:env.ADMIN_KEY,provider:'deepseek_flash',stream:true,messages:[{role:'user',content:'Chào'}]})}),env,{});
   assert.equal(streamed.status,200);assert.match(streamed.headers.get('Content-Type'),/text\/event-stream/);
   const reader=streamed.body.getReader();
   const firstChunk=await reader.read();assert.match(new TextDecoder().decode(firstChunk.value),/Xin chào/);
   await reader.cancel();
   const catalog=await call('/api/provider/catalog',{});
   for(const entry of first.entries)assert.equal(catalog.entries.find(e=>e.id===entry.id).thinking_enabled,entry.thinking_enabled);
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });
}

for(const [name,worker] of [['Dashboard work.js',dashboard],['server worker.js',server]]){
 test(`${name}: blank model preserves existing provider configuration`,async()=>{
  const env={DB:database(),ADMIN_KEY:'test-admin-key-with-enough-length'};
  async function call(models){
   const response=await worker.fetch(new Request('https://example.workers.dev/api/admin/providers/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'admin',key:env.ADMIN_KEY,providers:{},models})}),env,{});
   assert.equal(response.status,200,await response.text());
  }
  await call({deepseek:'deepseek-flash'});
  await call({deepseek:'',gemini:''});
  const response=await worker.fetch(new Request('https://example.workers.dev/api/admin/providers/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'admin',key:env.ADMIN_KEY})}),env,{});
  const status=await response.json();assert.equal(status.providers.deepseek.model,'deepseek-flash');
 });
}

for(const [name,worker] of [['Dashboard work.js',dashboard],['server worker.js',server]]){
 test(`${name}: image requests use Flash with the shared DeepSeek key`,async()=>{
  const env={DB:database(),ADMIN_KEY:'test-admin-key-with-enough-length',DEEPSEEK_API_KEY:'test-shared-deepseek-key'};
  const original=globalThis.fetch,seen=[];
  const image={type:'image_url',image_url:{url:'data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=='}};
  try{
   globalThis.fetch=async(url,options)=>{
    assert.equal(url,'https://api.deepseek.com/chat/completions');
    assert.equal(options.headers.Authorization,'Bearer '+env.DEEPSEEK_API_KEY);
    const body=JSON.parse(options.body);seen.push(body);
    assert.equal(body.model,'deepseek-flash');assert.equal(body.thinking.type,'disabled');
    assert.deepEqual(body.messages[0].content,[{type:'text',text:'Đọc bảng số liệu'},image]);
    return Response.json({choices:[{message:{content:'Đã đọc bảng'}}]});
   };
   for(const provider of ['deepseek','deepseek_flash','deepseek_pro','deepseek_r1']){
    const response=await worker.fetch(new Request('https://example.workers.dev/api/provider/model',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'admin',key:env.ADMIN_KEY,provider,messages:[{role:'user',content:[{type:'text',text:'Đọc bảng số liệu'},image]}]})}),env,{});
    assert.equal(response.status,200,await response.text());
   }
   assert.equal(seen.length,4);
   const rejected=await worker.fetch(new Request('https://example.workers.dev/api/provider/model',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'admin',key:env.ADMIN_KEY,provider:'deepseek_flash',messages:[{role:'system',content:[image]}]})}),env,{});
   assert.equal(rejected.status,400);assert.equal(seen.length,4);
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });
}
