import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import * as root from '../../work.js';
import * as server from '../worker.js';
function database(){const raw=new DatabaseSync(':memory:');return {raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return raw.prepare(sql).run(...this.args);},async first(){return raw.prepare(sql).get(...this.args)||null;}};},async batch(items){return Promise.all(items.map(i=>i.run()));}};}
function wav(){const b=Buffer.alloc(44+12800);b.write('RIFF');b.writeUInt32LE(b.length-8,4);b.write('WAVE',8);b.write('fmt ',12);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(16000,24);b.writeUInt32LE(32000,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(12800,40);for(let i=44;i<b.length;i+=2)b.writeInt16LE(Math.round(2000*Math.sin((i-44)*Math.PI/40)),i);return b;}
for(const [name,mod] of [['root',root],['server',server]]){
 test(`${name}: Whisper receives Vietnamese WAV and consumes one quota reservation`,async()=>{
  const db=database();let calls=0;
  try{
   const env={DB:db,AI:{run:async(model,input)=>{calls++;assert.equal(model,'@cf/openai/whisper-large-v3-turbo');assert.equal(input.language,'vi');assert.equal(input.task,'transcribe');assert.equal(input.audio,wav().toString('base64'));return {text:' Xin chào '};}}};
   const result=await mod.transcribeAudio(env,{username:'alice'},{audio:wav().toString('base64')});
   assert.equal(result.status,200);assert.equal((await result.json()).text,'Xin chào');assert.equal(calls,1);
   assert.equal(db.raw.prepare('SELECT used FROM cloud_daily').get().used,1);
  }finally{db.raw.close();}
 });
 test(`${name}: silence never reaches Whisper or consumes quota`,async()=>{
  let calls=0;const silent=wav();silent.fill(0,44);
  const result=await mod.transcribeAudio({AI:{run:async()=>{calls++;}}},{username:'alice'},{audio:silent.toString('base64')});
  assert.equal(result.status,422);assert.equal(calls,0);
 });
 test(`${name}: invalid audio is rejected before upstream call`,async()=>{
  let calls=0;const env={AI:{run:async()=>{calls++;}}};
  for(const audio of ['bad',Buffer.from('not wav'.repeat(100)).toString('base64'),'A'.repeat(1280104)]){
   assert.equal((await mod.transcribeAudio(env,{username:'alice'},{audio})).status,400);
  }
  assert.equal(calls,0);
 });
 test(`${name}: quota exhaustion never calls Whisper`,async()=>{
  const db=database();let calls=0;
  try{
   const env={DB:db,CLOUD_DAILY_REQUEST_LIMIT:1,AI:{run:async()=>{calls++;return {text:'Chào'};}}};
   await mod.transcribeAudio(env,{username:'alice'},{audio:wav().toString('base64')});
   assert.equal((await mod.transcribeAudio(env,{username:'alice'},{audio:wav().toString('base64')})).status,429);
   assert.equal(calls,1);
  }finally{db.raw.close();}
 });
 test(`${name}: failed recognition returns a useful error without retry`,async()=>{
  const db=database();let calls=0;
  try{const env={DB:db,AI:{run:async()=>{calls++;throw new Error('provider unavailable');}}};
   assert.equal((await mod.transcribeAudio(env,{username:'alice'},{audio:wav().toString('base64')})).status,503);assert.equal(calls,1);
  }finally{db.raw.close();}
 });
}

for (const mod of [root,server]) test("subscription caption from Android screenshot is suppressed",()=>{assert.equal(mod.cleanSpeechTranscript("Hãy subscribe cho kênh La La School Để không bỏ lỡ những video hấp dẫn"),"");assert.equal(mod.cleanSpeechTranscript("Kênh La La School là gì?"),"Kênh La La School là gì?");});

for(const [name,mod] of [['root',root],['server',server]]){
 test(`${name}: configured Groq receives WAV once, bypassing Workers inference`,async()=>{
  const db=database();let calls=0;
  try{
   const env={DB:db,GROQ_API_KEY:'test-secret',AI:{run:()=>assert.fail('Must not call Workers AI')}};
   const result=await mod.transcribeAudio(env,{username:'alice'},{audio:wav().toString('base64')},async(url,request)=>{
    calls++;assert.equal(url,'https://api.groq.com/openai/v1/audio/transcriptions');
    assert.equal(request.headers.Authorization,'Bearer test-secret');
    assert.equal(request.body.get('language'),'vi');assert.equal(request.body.get('model'),'whisper-large-v3-turbo');
    assert.deepEqual(Buffer.from(await request.body.get('file').arrayBuffer()),wav());
    return Response.json({text:'Xin chào bạn'});
   });
   assert.equal(result.status,200);assert.equal((await result.json()).text,'Xin chào bạn');assert.equal(calls,1);
  }finally{db.raw.close();}
 });
 test(`${name}: Groq rejection returns actionable code without another transcription`,async()=>{
  const db=database();let calls=0;
  try{
   const env={DB:db,GROQ_API_KEY:'test-secret',AI:{run:()=>assert.fail('No automatic fallback')}};
   const result=await mod.transcribeAudio(env,{username:'alice'},{audio:wav().toString('base64')},async()=>{calls++;return new Response('',{status:429});});
   assert.equal(result.status,503);assert.equal((await result.json()).code,'VOICE_UPSTREAM_LIMIT');assert.equal(calls,1);
  }finally{db.raw.close();}
 });
 test(`${name}: stalled transcription returns bounded timeout, no automatic retry`,async(t)=>{
  const db=database();let calls=0;let entered;
  const started=new Promise(resolve=>entered=resolve);
  t.mock.timers.enable({apis:['setTimeout']});
  try{
   const pending=mod.transcribeAudio({DB:db,AI:{run:()=>{calls++;entered();return new Promise(()=>{});}}},{username:'alice'},{audio:wav().toString('base64')});
   await started;t.mock.timers.tick(40000);
   const result=await pending;
   assert.equal(result.status,503);assert.equal((await result.json()).code,'VOICE_UPSTREAM_TIMEOUT');assert.equal(calls,1);
  }finally{t.mock.timers.reset();db.raw.close();}
 });
}
