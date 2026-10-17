import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {mediaAPI} from '../../work.js';
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
