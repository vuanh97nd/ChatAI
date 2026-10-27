import {test} from 'node:test';
import assert from 'node:assert/strict';
import {videoOptions} from '../work.js';
test('video length and frame follow the request',()=>{
 assert.deepEqual(videoOptions({seconds:8,frame:'landscape'},'x'),{seconds:8,size:'1280x720'});
 assert.deepEqual(videoOptions({},'Tạo video 12 giây cảnh Vịnh Hạ Long khung ngang'),{seconds:12,size:'1280x720'});
 assert.deepEqual(videoOptions({},'tạo video 10 giây'),{seconds:8,size:'720x1280'});
 assert.deepEqual(videoOptions({},'tạo video cánh đồng lúa'),{seconds:4,size:'720x1280'});
 assert.equal(videoOptions({seconds:30},'x').seconds,12);
});
