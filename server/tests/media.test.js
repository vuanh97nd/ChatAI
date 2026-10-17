import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {mediaAPI,synthesizeSpeech} from '../../work.js';
function database(){const raw=new DatabaseSync(':memory:');raw.exec('CREATE TABLE support_rate(key TEXT PRIMARY KEY,hits INTEGER,bucket INTEGER)');return {raw,prepare(sql){return {args:[],bind(...a){this.args=a;return this;},async run(){return raw.prepare(sql).run(...this.args);},async first(){return raw.prepare(sql).get(...this.args)||null;}};}};}
test('billing authority cannot generate media',async()=>{assert.equal((await mediaAPI({BILLING_ROLE:'authority'},{username:'a'},'/api/media/image',{})).status,503);});
test('authenticated non-admin can generate images, subject to rate limit',async()=>{
 const db=database();let calls=0;const env={DB:db,AI:{run:async(model,input)=>{calls++;assert.equal(model,'@cf/black-forest-labs/flux-1-schnell');assert.equal(input.prompt,'A landscape');return {image:'aGVsbG8='};}}};
 for(let i=0;i<3;i++)assert.equal((await mediaAPI(env,{username:'alice'},'/api/media/image',{prompt:'A landscape'})).status,200);
 assert.equal((await mediaAPI(env,{username:'alice'},'/api/media/image',{prompt:'A landscape'})).status,429);assert.equal(calls,3);db.raw.close();
});
test('video creation is not repeated and content is owner restricted',async()=>{
 const db=database(),env={DB:db,OPENAI_API_KEY:'test-key'},id='12345678-1234-1234-1234-123456789abc';let calls=0;
 const send=async(url,opts)=>{calls++;assert.equal(opts.redirect,'manual');assert.equal(opts.headers.Authorization,'Bearer test-key');return Response.json({id:'video_test123',status:'queued'});};
 const input={prompt:'A wave',request_id:id};
 assert.equal((await mediaAPI(env,{username:'alice'},'/api/media/video/create',input,send)).status,200);
 assert.equal((await mediaAPI(env,{username:'alice'},'/api/media/video/create',input,send)).status,200);assert.equal(calls,1);
 assert.equal((await mediaAPI(env,{username:'bob'},'/api/media/video/content',{id},send)).status,409);assert.equal(calls,1);db.raw.close();
});
test('uncertain video submission is retained and never resubmitted',async()=>{
 const db=database(),env={DB:db,OPENAI_API_KEY:'test-key'},input={prompt:'A wave',request_id:'12345678-1234-1234-1234-123456789abc'};let calls=0;
 const send=async()=>{calls++;throw Error('timeout');};
 assert.equal((await mediaAPI(env,{username:'alice'},'/api/media/video/create',input,send)).status,502);
 const result=await mediaAPI(env,{username:'alice'},'/api/media/video/create',input,send);assert.equal((await result.json()).status,'unconfirmed');assert.equal(calls,1);db.raw.close();
});
test('definite provider rejection can be checked without allowing duplicate charges',async()=>{
 const db=database(),env={DB:db,OPENAI_API_KEY:'test-key'},input={prompt:'A wave',request_id:'12345678-1234-1234-1234-123456789abc'};
 await mediaAPI(env,{username:'alice'},'/api/media/video/create',input,async()=>new Response('',{status:403}));
 const status=await mediaAPI(env,{username:'alice'},'/api/media/video/status',{id:input.request_id});assert.equal((await status.json()).status,'failed');db.raw.close();
});

test('neural speech uses Vietnamese instructions and returns private audio',async()=>{
 const db=database();let calls=0;
 const result=await synthesizeSpeech({DB:db,OPENAI_API_KEY:'test-key'},{username:'alice'},{text:'Xin chào'},async(url,options)=>{
  calls++;assert.equal(url,'https://api.openai.com/v1/audio/speech');
  const input=JSON.parse(options.body);assert.equal(input.model,'gpt-4o-mini-tts');assert.match(input.instructions,/Vietnamese/);assert.equal(input.input,'Xin chào');
  return new Response(new Uint8Array([1,2,3]));
 });
 assert.equal(result.status,200);assert.equal(result.headers.get('Cache-Control'),'no-store');assert.equal(result.headers.get('Content-Type'),'audio/mpeg');assert.equal(calls,1);db.raw.close();
});
test('speech without provider key supports explicit local fallback',async()=>{
 const db=database();const response=await synthesizeSpeech({DB:db},{username:'alice'},{text:'Xin chào'},()=>{throw Error('Must not call provider');});assert.equal((await response.json()).code,'TTS_NOT_CONFIGURED');db.raw.close();
});
test('Gemini Vietnamese speech is wrapped in playable 24kHz WAV',async()=>{
 const db=database();const result=await synthesizeSpeech({DB:db,GEMINI_API_KEY:'test-gemini'},{username:'alice'},{text:'Xin chào',speech_provider:'gemini'},async(url,options)=>{
  assert.match(url,/gemini-2.5-flash-preview-tts:generateContent$/);assert.equal(options.headers['x-goog-api-key'],'test-gemini');
  assert.deepEqual(JSON.parse(options.body).generationConfig.responseModalities,['AUDIO']);
  return Response.json({candidates:[{content:{parts:[{inlineData:{mimeType:'audio/L16;codec=pcm;rate=24000',data:'AQIDBA=='}}]}}]});
 });
 assert.equal(result.headers.get('Content-Type'),'audio/wav');assert.equal(result.headers.get('X-ChatAI-Speech-Provider'),'gemini');
 const bytes=Buffer.from(await result.arrayBuffer());assert.equal(bytes.toString('ascii',0,4),'RIFF');assert.equal(bytes.readUInt32LE(24),24000);assert.equal(bytes.readUInt32LE(40),4);assert.deepEqual([...bytes.subarray(44)],[1,2,3,4]);db.raw.close();
});
test('unsupported speech provider never calls an API',async()=>{
 const response=await synthesizeSpeech({}, {username:'alice'}, {text:'Xin chào',speech_provider:'deepseek'},()=>{throw Error('Do not call');});assert.equal((await response.json()).code,'TTS_UNSUPPORTED');
});
test('automatic speech selects Gemini if only Gemini is configured',async()=>{
 const db=database();const response=await synthesizeSpeech({DB:db,GEMINI_API_KEY:'test-gemini'},{username:'alice'},{text:'Xin chào'},async(url)=>{
  assert.match(url,/googleapis/);return Response.json({candidates:[]});
 });assert.equal(response.status,502);db.raw.close();
});

test('Vietnamese image subject is translated before FLUX and preserved in its prompt',async()=>{
 const {mediaAPI:serverMedia}=await import('../worker.js');
 for(const handler of [mediaAPI,serverMedia]){
  const db=database(),calls=[];
  try{
   const env={DB:db,AI:{run:async(model,input)=>{
    calls.push({model,input});
    if(model.includes('qwen')){assert.equal(input.messages[1].content,'tạo ảnh con mèo');return {response:'A cat'};}
    assert.equal(input.prompt,'A cat');return {image:'aGVsbG8='};
   }}};
   const response=await handler(env,{username:'alice'},'/api/media/image',{prompt:'tạo ảnh con mèo'});
   assert.equal(response.status,200);assert.equal(calls.length,2);assert.ok(calls[1].model.includes('flux'));
  }finally{db.raw.close();}
 }
});
test('failed image translation never generates an unrelated image',async()=>{
 const db=database();let calls=0;
 try{
  const response=await mediaAPI({DB:db,AI:{run:async()=>{calls++;return {response:''};}}},{username:'alice'},'/api/media/image',{prompt:'tạo ảnh con mèo'});
  assert.equal(response.status,503);assert.equal((await response.json()).code,'IMAGE_PROMPT_TRANSLATION_FAILED');assert.equal(calls,1);
 }finally{db.raw.close();}
});
