// Worker accepts extracted data; document retrieval is tested in desktop Python.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as dashboard from '../work.js';
import * as server from '../server/worker.js';
for (const [name, api] of [['dashboard',dashboard],['server',server]]) {
 test(`${name}: document contract preserves missing values and provenance`,()=>{
  const contract=api.extractionContract('document'),record=contract.schema.properties.records.items;
  assert.deepEqual(record.required,['label','value','unit','source','missing']);
  assert.ok(record.properties.value.type.includes('null'));
  assert.equal(record.additionalProperties,false);
  assert.match(contract.instructions,/không suy đoán dữ liệu thiếu/);
  assert.match(contract.instructions,/không có quyền/);
 });
 test(`${name}: search preserves source identity without claiming full document`,async()=>{
  let requested;
  const result=await api.requestWebSearch({BRAVE_SEARCH_API_KEY:'test-only-key'},'RFC 9110',async url=>{
   requested=new URL(url);
   return Response.json({web:{results:[{title:'HTTP Semantics',url:'https://www.rfc-editor.org/rfc/rfc9110',description:'HTTP specification'}]}});
  });
  assert.equal(requested.searchParams.get('q'),'RFC 9110');
  assert.equal(result.sources[0].url,'https://www.rfc-editor.org/rfc/rfc9110');
  assert.equal(result.sources[0].title,'HTTP Semantics');
  assert.notEqual(result.full_document,true);
 });
 test(`${name}: invalid queries and missing credentials do not send requests`,async()=>{
  const send=()=>{throw Error('must not fetch');};
  for(const query of ['', 'a'.repeat(601)])await assert.rejects(api.requestWebSearch({BRAVE_SEARCH_API_KEY:'test-only-key'},query,send));
  await assert.rejects(api.requestWebSearch({},'RFC 9110',send),/BRAVE_SEARCH_API_KEY/);
 });
 test(`${name}: upstream failure redacts the search key`,async()=>{
  await assert.rejects(api.requestWebSearch({BRAVE_SEARCH_API_KEY:'test-only-key'},'RFC 9110',async()=>Response.json({message:'test-only-key denied'},{status:403})),error=>{
   assert.ok(!error.message.includes('test-only-key'));return true;
  });
 });
}
