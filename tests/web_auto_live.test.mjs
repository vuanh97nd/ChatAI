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

import {liveCard} from '../work.js';
test('liveCard turns lookups into drawable data',async()=>{
 const send=async url=>new Response(JSON.stringify(String(url).includes('geocoding')
  ?{results:[{name:'Đà Lạt',admin1:'Lâm Đồng',country:'Việt Nam',latitude:11.9,longitude:108.4}]}
  :{timezone:'Asia/Bangkok',current:{time:'2026-10-28T08:00',temperature_2m:18.4,relative_humidity_2m:88,weather_code:61,wind_speed_10m:7},current_units:{},
    daily:{time:['2026-10-28','2026-10-29'],temperature_2m_max:[22,23],temperature_2m_min:[15,16],precipitation_probability_max:[70,40],weather_code:[61,3]},daily_units:{}}),{status:200});
 const card=liveCard(await autoLiveSearch('Thời tiết ở Đà Lạt ngày mai',send));
 assert.equal(card.kind,'weather');assert.match(card.place,/Đà Lạt/);
 assert.equal(card.current.temperature,18.4);assert.equal(card.daily.length,2);assert.deepEqual(card.daily[0],{date:'2026-10-28',max:22,min:15,rain:70,code:61});
 assert.equal(liveCard(null),null);
});
