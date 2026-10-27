import {test} from 'node:test';
import assert from 'node:assert/strict';
import {liveIntent,weatherPlace,autoLiveSearch} from '../work.js';

test('detects weather, gold and news questions without the web toggle',()=>{
 assert.equal(liveIntent('Sáng nay Hà Nội có mưa không?'),'weather');
 assert.equal(liveIntent('Thời tiết Đà Nẵng ngày mai'),'weather');
 assert.equal(liveIntent('giá vàng nhẫn hôm nay bao nhiêu'),'gold');
 assert.equal(liveIntent('Có tin tức gì mới về bão không'),'news');
});
test('ignores technical questions that only share a word',()=>{
 assert.equal(liveIntent('Giá trị hệ số an toàn của mái đê là bao nhiêu?'),null);
 assert.equal(liveIntent('Viết email gửi tư vấn giám sát'),null);
});
test('extracts the place, defaulting to Hà Nội',()=>{
 assert.equal(weatherPlace('Thời tiết ở Đà Lạt hôm nay'),'Đà Lạt');
 assert.equal(weatherPlace('Sài Gòn có mưa không'),'Hồ Chí Minh');
 assert.equal(weatherPlace('Trời có mưa không?'),'Hà Nội');
});
test('weather question calls Open-Meteo and returns sourced data',async()=>{
 const calls=[];
 const send=async url=>{calls.push(String(url));const body=String(url).includes('geocoding')
  ?{results:[{name:'Huế',admin1:'Thừa Thiên Huế',country:'Việt Nam',latitude:16.46,longitude:107.59}]}
  :{timezone:'Asia/Bangkok',current:{time:'2026-10-28T08:00',temperature_2m:26},current_units:{},daily:{},daily_units:{}};
  return new Response(JSON.stringify(body),{status:200});};
 const result=await autoLiveSearch('Thời tiết ở Huế thế nào',send);
 assert.equal(result.auto,'weather');
 assert.ok(calls.some(u=>u.includes('api.open-meteo.com')));
 assert.match(result.answer,/Open-Meteo/);
 assert.equal(await autoLiveSearch('Viết code Python',send),null);
});
