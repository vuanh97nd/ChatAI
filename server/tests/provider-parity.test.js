import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import dashboard from '../../work.js';
import server from '../worker.js';
function database(){
 const raw=new DatabaseSync(':memory:');
 return {raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return {meta:{changes:Number(raw.prepare(sql).run(...this.args).changes)}};},async first(){return raw.prepare(sql).get(...this.args)||null;},async all(){return {results:raw.prepare(sql).all(...this.args)};}};},async batch(items){return Promise.all(items.map(item=>item.run()));}};
}
const ADMIN='test-admin-key-with-enough-length';
const environment=()=>({DB:database(),ADMIN_KEY:ADMIN,NVIDIA_API_KEY:'test-nvidia',GROQ_API_KEY:'test-groq',GEMINI_API_KEY:'test-gemini'});
const call=(worker,env,body,path='/api/provider/model')=>worker.fetch(new Request('https://example.org'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'admin',key:ADMIN,...body})}),env,{});
const tinyJpeg='/9j/'+'A'.repeat(200);

for(const [name,worker] of [['Dashboard work.js',dashboard],['server worker.js',server]]){
 for(const [provider,host] of [['nvidia','integrate.api.nvidia.com'],['groq','api.groq.com']])test(`${name}: ${provider} planning requests use JSON mode`,async()=>{
  const env=environment(),original=globalThis.fetch;let seen;
  try{
   globalThis.fetch=async(url,options)=>{seen={url,payload:JSON.parse(options.body)};return Response.json({choices:[{message:{content:'{"answer":"OK","tool":"","arguments":{}}'}}]});};
   const response=await call(worker,env,{provider,format:{type:'object'},messages:[{role:'user',content:'Lập kế hoạch'}]});
   assert.equal(response.status,200);
   assert.ok(seen.url.includes(host),seen.url);
   assert.equal(seen.payload.response_format.type,'json_object');
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });

 test(`${name}: a model that rejects JSON mode is retried without it`,async()=>{
  const env=environment(),original=globalThis.fetch,payloads=[];
  try{
   globalThis.fetch=async(url,options)=>{
    payloads.push(JSON.parse(options.body));
    return payloads.length===1?new Response('{"error":"response_format unsupported"}',{status:400}):Response.json({choices:[{message:{content:'{"answer":"OK","tool":"","arguments":{}}'}}]});
   };
   const response=await call(worker,env,{provider:'nvidia',format:{type:'object'},messages:[{role:'user',content:'Lập kế hoạch'}]});
   assert.equal(response.status,200);
   assert.equal(payloads.length,2);
   assert.ok(payloads[0].response_format);assert.equal(payloads[1].response_format,undefined);
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });

 test(`${name}: Gemini planning asks for JSON and no Flash thinking`,async()=>{
  const env=environment(),original=globalThis.fetch;let payload;
  try{
   globalThis.fetch=async(url,options)=>{payload=JSON.parse(options.body);return Response.json({candidates:[{content:{parts:[{text:'{"answer":"OK","tool":"","arguments":{}}'}]}}]});};
   const response=await call(worker,env,{provider:'gemini',format:{type:'object'},messages:[{role:'user',content:'Lập kế hoạch'}]});
   assert.equal(response.status,200);
   assert.equal(payload.generationConfig.responseMimeType,'application/json');
   assert.equal(payload.generationConfig.thinkingConfig.thinkingBudget,0);
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });

 test(`${name}: Gemini model catalog is listed`,async()=>{
  const env=environment(),original=globalThis.fetch;let seen;
  try{
   globalThis.fetch=async(url,options)=>{seen={url,headers:options.headers};return Response.json({models:[{name:'models/gemini-2.5-flash'},{name:'models/gemini-2.5-pro'}]});};
   const response=await call(worker,env,{provider:'gemini',api_key:'test-gemini'},'/api/admin/providers/models');
   const value=await response.json();
   assert.equal(response.status,200,JSON.stringify(value));
   assert.ok(seen.url.startsWith('https://generativelanguage.googleapis.com/'));
   assert.equal(seen.headers['x-goog-api-key'],'test-gemini');
   assert.deepEqual(value.models,['gemini-2.5-flash','gemini-2.5-pro']);
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });

 test(`${name}: more than two images in one turn are accepted`,async()=>{
  const env=environment(),original=globalThis.fetch;let payload;
  try{
   globalThis.fetch=async(url,options)=>{payload=JSON.parse(options.body);return Response.json({choices:[{message:{content:'OK'}}]});};
   const images=Array.from({length:5},()=>({type:'image_url',image_url:{url:'data:image/jpeg;base64,'+tinyJpeg}}));
   const response=await call(worker,env,{provider:'nvidia',messages:[{role:'user',content:[{type:'text',text:'Đọc ảnh'},...images]}]});
   assert.equal(response.status,200,JSON.stringify(await response.clone().json()));
   assert.equal(payload.messages.at(-1).content.filter(p=>p.type==='image_url').length,5);
  }finally{globalThis.fetch=original;env.DB.raw.close();}
 });
}
