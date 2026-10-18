import {test} from 'node:test';
import assert from 'node:assert/strict';
import {requestFreeSpecialist} from '../../work.js';
test('news uses a fixed RSS source, rejects external links and caches results',async()=>{
 let calls=0;
 const send=async url=>{calls++;assert.equal(url,'https://vnexpress.net/rss/tin-moi-nhat.rss');return new Response('<rss><channel><item><title><![CDATA[Tin mới]]></title><link>https://vnexpress.net/article.html</link><description>Mô tả</description><pubDate>today</pubDate></item><item><title>Bad</title><link>https://evil.example/a</link></item></channel></rss>');};
 const result=await requestFreeSpecialist('news','Tin mới test',send);
 assert.equal(result.sources.length,1);assert.match(result.answer,/Tin mới/);
 await requestFreeSpecialist('news','Tin mới test',send);assert.equal(calls,1);
});
test('knowledge uses Wikipedia and returns attributed extracts',async()=>{
 const result=await requestFreeSpecialist('knowledge','Quang hợp là gì?',async url=>{
  const u=new URL(url);assert.equal(u.hostname,'vi.wikipedia.org');assert.equal(u.searchParams.get('gsrsearch'),'Quang hợp');
  return Response.json({query:{pages:{1:{title:'Quang hợp',fullurl:'https://vi.wikipedia.org/wiki/Quang_hop',extract:'Plants convert light energy.'}}}});
 });
 assert.match(result.answer,/Plants convert/);assert.equal(result.sources.length,1);
});
test('specialist failure does not fall back to another or paid service',async()=>{
 let calls=0;await assert.rejects(requestFreeSpecialist('news','Failure test',async()=>{calls++;return new Response('down',{status:503});}));assert.equal(calls,1);
});

test('gold prices preserve PNJ units and never fabricate a publication timestamp',async()=>{
 const {requestGoldPrice}=await import('../../work.js');
 const result=await requestGoldPrice(async url=>{
  assert.equal(url,'https://www.pnj.com.vn/blog/gia-vang/');
  return new Response('<h2>Cập nhật ngày: <span id="time-now"></span></h2><table><th>Loại vàng | ĐVT: 1.000đ/Chỉ</th><tbody id="content-price"><tr><td>Vàng miếng SJC</td><td><span>14,060</span></td><td>14,360</td></tr></tbody></table>');
 });
 assert.equal(result.items[0].buy,'14,060');assert.equal(result.unit,'1.000 đồng/chỉ');assert.equal(result.updated_at,null);assert.match(result.answer,/không xác nhận/);
 await assert.rejects(requestGoldPrice(async()=>new Response('no price table')),/đổi cấu trúc/);
});
