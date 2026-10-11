import {test} from 'node:test';
import assert from 'node:assert/strict';
import {requestWebSearch as deployed} from '../../work.js';
import {requestWebSearch as reference} from '../worker.js';
for(const [name,search] of [['deployed',deployed],['reference',reference]]){
 test(name+' uses Bing RSS and keeps verified source links',async()=>{
  const result=await search({},'PLAXIS',async(url,options)=>{
   const u=new URL(url);assert.equal(u.hostname,'www.bing.com');assert.equal(u.searchParams.get('format'),'rss');assert.equal(options.headers['X-Subscription-Token'],undefined);
   return new Response('<rss><channel><item><title>A &amp; B</title><link>https://example.com/a?q=1&amp;x=2</link><description><![CDATA[<b>Verified</b> snippet]]></description></item><item><link>javascript:alert(1)</link><description>bad</description></item></channel></rss>');
  });
  assert.equal(result.source,'bing_search');assert.deepEqual(result.sources,[{title:'A & B',url:'https://example.com/a?q=1&x=2'}]);assert.match(result.answer,/Verified snippet/);
 });
 test(name+' falls back to Bing HTML when RSS is empty',async()=>{
  let calls=0;
  const result=await search({},'thời tiết Hà Nội',async(url)=>{
   calls++;
   if(calls===1)return new Response('<rss><channel></channel></rss>');
   assert.equal(new URL(url).searchParams.has('format'),false);
   const encoded='a1'+btoa('https://example.com/weather');
   return new Response(`<html><li class="b_algo"><h2><a href="https://www.bing.com/ck/a?u=${encoded}">Weather</a></h2><p>Forecast snippet</p></li><li class="b_algo"><h2><a href="javascript:alert(1)">Bad</a></h2><p>Ignore</p></li></html>`);
  });
  assert.equal(calls,2);assert.equal(result.sources.length,1);
  assert.equal(result.sources[0].url,'https://example.com/weather');
  assert.match(result.answer,/Forecast snippet/);
 });
 test(name+' rejects blocked, challenge and empty results',async()=>{
  for(const response of [new Response('blocked',{status:403}),new Response('<html>captcha</html>'),new Response('<rss><channel></channel></rss>')]) await assert.rejects(search({},'query',async()=>response.clone()),/Bing/);
 });
}
