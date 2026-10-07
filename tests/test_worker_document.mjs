import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const worker=await readFile(new URL('../work.js',import.meta.url),'utf8');
const api=await import('data:text/javascript;base64,'+Buffer.from(worker).toString('base64'));
const cases=JSON.parse(await readFile(new URL('./document_cases.json',import.meta.url),'utf8'));
for(const c of cases){
 const queries=api.documentQueries({target:c.target,identifiers:{},need_fulltext:true});
 assert.ok(queries.length>=2&&queries.length<=3);
 queries.forEach(q=>assert.doesNotMatch(q,/^(tóm tắt|tìm |giải thích|phân tích|so sánh|trích |dịch )/i));
}
assert.equal(api.documentScore({title:'Công cụ online',url:'https://example.gov.vn'}, {target:'Attention Is All You Need'}),0);
assert.equal(api.documentScore({title:'ISO 14001',url:'https://iso.org'}, {target:'ISO 9001',identifiers:{codes:['ISO 9001']}}),0);
const html=await api.readDocumentWeb({},'https://example.org/paper',async()=>new Response('<html><body>Attention Is All You Need '+ 'document content '.repeat(2000)+'</body></html>',{headers:{'content-type':'text/html'}}));
assert.ok(html.text.length>7000);assert.equal(html.full_document,false);
const raw=Buffer.from('%PDF-binary-test');let received;
const binary=await api.readDocumentWeb({DOCUMENT_READER:{fetch:async r=>{received=Buffer.from(await r.arrayBuffer());return Response.json({text:'complete',full_document:true,pages:[{page:1,text:'complete'}]});}}},'https://example.org/file.pdf',async()=>new Response(raw,{headers:{'content-type':'application/pdf'}}));
assert.deepEqual(received,raw);assert.equal(binary.full_document,true);
await assert.rejects(api.readDocumentWeb({},'https://127.0.0.1/secret',async()=>{throw Error('must not fetch');}));
const env={AI:{run:async()=>({response:JSON.stringify({task:'summarize',target:'QXYZ 777:2099',target_type:'document',identifiers:{codes:['QXYZ 777:2099'],years:['2099'],issuers:[],authors:[]},need_web:true,need_fulltext:true,standalone_question:'Tóm tắt QXYZ 777:2099',assumption:''})})},BRAVE_SEARCH_API_KEY:'test-key'};
const empty=await api.documentResearch(env,'Tóm tắt QXYZ 777:2099',[],async()=>Response.json({web:{results:[]}}));
assert.equal(empty.not_found,true);assert.equal(empty.documents.length,0);
console.log('Worker: 20 query cases + relevance, full HTML, raw binary, private URL and no-results checks passed.');
