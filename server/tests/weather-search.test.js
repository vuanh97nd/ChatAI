import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as root from '../../work.js';
import * as reference from '../worker.js';
for(const [name,mod] of [['root',root],['reference',reference]]){
 test(`${name}: weather uses geocoding and dated forecast with source`,async()=>{
  let calls=0;
  const result=await mod.requestWeatherSearch('Hà Nội',async(url)=>{
   const u=new URL(url);calls++;
   if(calls===1){assert.equal(u.hostname,'geocoding-api.open-meteo.com');assert.equal(u.searchParams.get('name'),'Hà Nội');return Response.json({results:[{name:'Hà Nội',country:'Việt Nam',latitude:21.02,longitude:105.84}]});}
   assert.equal(u.hostname,'api.open-meteo.com');assert.equal(u.searchParams.get('latitude'),'21.02');assert.equal(u.searchParams.get('forecast_days'),'3');
   return Response.json({timezone:'Asia/Ho_Chi_Minh',current:{time:'2026-10-16T18:00',temperature_2m:28},daily:{time:['2026-10-16','2026-10-17'],temperature_2m_max:[30,31]},current_units:{temperature_2m:'°C'}});
  });
  assert.equal(calls,2);assert.equal(result.source,'open_meteo');assert.match(result.answer,/2026-10-16T18:00/);assert.match(result.answer,/28/);assert.equal(new URL(result.sources[0].url).hostname,'api.open-meteo.com');
 });
 test(`${name}: unknown location and missing temperatures fail rather than fabricate`,async()=>{
  await assert.rejects(mod.requestWeatherSearch('',()=>{throw new Error('unexpected');}));
  await assert.rejects(mod.requestWeatherSearch('unknown',async()=>Response.json({results:[]})),/địa điểm/);
  let calls=0;await assert.rejects(mod.requestWeatherSearch('Paris',async()=>Response.json(++calls===1?{results:[{latitude:48.85,longitude:2.35}]}:{current:{time:'now'}})),/số liệu/);
 });
 test(`${name}: speech cleanup removes known caption but preserves legitimate channel question`,()=>{
  assert.equal(mod.cleanSpeechTranscript('Thời tiết Hà Nội hôm nay? Các bạn hãy đăng ký cho kênh lalaschool để không bỏ lỡ những video hấp dẫn.'),'Thời tiết Hà Nội hôm nay?');
  assert.equal(mod.cleanSpeechTranscript('Kênh Lalaschool là gì?'),'Kênh Lalaschool là gì?');
  assert.equal(mod.cleanSpeechTranscript('Lalaschool'),'');
 });
}

test('GPS weather uses validated coordinates without geocoding a fabricated city',async()=>{
 let calls=0;
 const result=await root.requestWeatherSearch('Vị trí hiện tại',async(url)=>{
  calls++;const u=new URL(url);assert.equal(u.hostname,'api.open-meteo.com');assert.equal(u.searchParams.get('latitude'),'21.02');
  return Response.json({current:{time:'2026-10-17T10:00',temperature_2m:25}});
 },{latitude:21.02,longitude:105.84});
 assert.equal(calls,1);assert.match(result.answer,/gần đúng/);
 await assert.rejects(root.requestWeatherSearch('GPS',()=>{throw Error('must not fetch');},{latitude:999,longitude:0}),/Tọa độ/);
});

test('generic subscribe hallucination is removed without deleting real channel questions',()=>{
 for(const mod of [root,reference]){
  assert.equal(mod.cleanSpeechTranscript('Các bạn hãy đăng ký kênh để ủng hộ kênh của mình nhé.'),'');
  assert.equal(mod.cleanSpeechTranscript('Thời tiết hôm nay? Các bạn hãy đăng ký kênh để ủng hộ kênh của mình nhé.'),'Thời tiết hôm nay?');
  const real='Vì sao AI nói các bạn hãy đăng ký kênh để ủng hộ kênh của mình nhé?';
  assert.equal(mod.cleanSpeechTranscript(real),real);
  assert.equal(mod.cleanSpeechTranscript('Làm sao đăng ký kênh để ủng hộ tác giả?'),'Làm sao đăng ký kênh để ủng hộ tác giả?');
 }
});
