import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import * as root from '../../work.js';
import * as server from '../worker.js';
function database(){const raw=new DatabaseSync(':memory:');return {raw,prepare(sql){return {args:[],bind(...args){this.args=args;return this;},async run(){return raw.prepare(sql).run(...this.args);},async first(){return raw.prepare(sql).get(...this.args)||null;}};},async batch(items){return Promise.all(items.map(i=>i.run()));}};}
function wav(){const b=Buffer.alloc(44+6400);b.write('RIFF');b.writeUInt32LE(b.length-8,4);b.write('WAVE',8);b.write('fmt ',12);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(16000,24);b.writeUInt32LE(32000,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(6400,40);return b;}
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
