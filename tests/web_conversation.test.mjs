import {test} from 'node:test';
import assert from 'node:assert/strict';
import {conversationAPI} from '../work.js';
function database(owner='alice') {
 const writes=[];
 return {writes,batch:async()=>[],prepare(sql){let args=[];return {bind(...values){args=values;return this;},first:async()=>args[1]===owner?{id:'conversation-1',title:'Original'}:null,run:async()=>{writes.push({sql,args});return{meta:{changes:1}};}};}};
}
test('rename only modifies a conversation belonging to authenticated owner',async()=>{
 const db=database();const result=await conversationAPI('/api/conversations/rename',{conversation_id:'conversation-1',title:'  Kế hoạch mới  '},{username:'alice'},db);
 assert.equal(result.status,200);assert.equal((await result.json()).title,'Kế hoạch mới');assert.equal(db.writes.length,1);
 assert.deepEqual(db.writes[0].args.slice(2),['conversation-1','alice']);
});
test('rename rejects a different owner and invalid titles without any update',async()=>{
 const db=database();const other=await conversationAPI('/api/conversations/rename',{conversation_id:'conversation-1',title:'Stolen'},{username:'bob'},db);
 assert.equal(other.status,404);
 for(const title of ['', ' ', 'a'.repeat(151), null]){
  const result=await conversationAPI('/api/conversations/rename',{conversation_id:'conversation-1',title},{username:'alice'},db);assert.equal(result.status,400);
 }
 assert.equal(db.writes.length,0);
});
