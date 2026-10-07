import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../work.js',import.meta.url),'utf8');
const {reserveCloud}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
let daily=0;
const db={batch:async()=>[],prepare(sql){
 assert(!/UPDATE cloud_trials/.test(sql),'Old checked lifetime counter must not be modified');
 return {bind(...args){this.args=args;return this;},run:async()=>({success:true}),async first(){
   if(sql.includes('UPDATE cloud_daily'))return daily<this.args[1]?{used:++daily}:null;
   throw Error('Unexpected query: '+sql);
 }};
}};
for(let i=0;i<20;i++)assert.equal(await reserveCloud({DB:db,CLOUD_DAILY_REQUEST_LIMIT:20},'existing-owner-used-3'),null);
const limit=await reserveCloud({DB:db,CLOUD_DAILY_REQUEST_LIMIT:20},'existing-owner-used-3');
assert.equal(limit.status,429);assert.equal((await limit.json()).code,'CLOUD_BUSY');
assert(!source.includes('used<3'));assert(!source.includes('quota.used>=3'));assert(!source.includes('MIN(3,used'));
console.log('PASS: 20 calls allowed after old quota; daily budget remains active.');
