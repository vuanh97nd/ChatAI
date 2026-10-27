import {test} from 'node:test';
import assert from 'node:assert/strict';
import {billingMappedActor} from '../work.js';
const env={BILLING_ACCOUNT_MAP:JSON.stringify({anhvn:'anhvn',olduser:'kien2750'})};
const who=name=>({username:name,created_at:'2026-01-01',updated_at:'2026-01-01'});
test('mapped accounts keep their explicit wallet',()=>{
 assert.equal(billingMappedActor(env,who('olduser')).username,'kien2750');
 assert.equal(billingMappedActor(env,who('anhvn')).username,'anhvn');
});
test('new accounts get a same-name wallet',()=>{
 assert.equal(billingMappedActor(env,who('newbie')).username,'newbie');
});
test('a name already owned by another mapped account is not auto-assigned',()=>{
 assert.throws(()=>billingMappedActor(env,who('kien2750')),/not explicitly mapped/);
});
test('auto mapping can be turned off',()=>{
 assert.throws(()=>billingMappedActor({...env,BILLING_AUTO_MAP:'false'},who('newbie')),/not explicitly mapped/);
});
