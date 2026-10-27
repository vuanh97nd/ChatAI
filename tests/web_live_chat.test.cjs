const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const live = source.slice(source.indexOf('async function liveReply('), source.indexOf('\nfunction sendMessage('));
const send = source.slice(source.indexOf('function sendMessage('), source.indexOf('\nfunction regenerate('));
const regen = source.slice(source.indexOf('function regenerate('), source.indexOf('\ndocument.querySelector("#newChat")'));
const stop = source.slice(source.indexOf('function stopStream('), source.indexOf('\nfunction streamText('));
let calls = [], rows = [], state;
function node() { return { textContent: '', append() {}, remove() {}, classList: { add() {}, remove() {} }, setAttribute() {} }; }
function context(fetch) {
  calls = []; rows = [];
  state = { LIVE:true, model:{id:'cloudflare'}, streaming:null, memoryOn:false, guestToken:'a'.repeat(64), session:null,
    attachment:null, clearAttachment(){state.attachment=null;}, toast(){}, setGenerating(){}, renderRichText(){}, GUEST_LIMIT:3, guestTurns:0, activeId:-1, conversations:[], crypto, AbortController, TextDecoder, clearInterval,
    els:{sendBtn:node(), messages:{lastElementChild:node()}, followups:{}, input:{value:'',style:{}}, search:{value:''}},
    fetch: async (url, options) => { calls.push({url,...options,payload:JSON.parse(options.body)}); return fetch(url,options); },
    addMessage(role,text) { const row={role,text,p:node(),body:node()};rows.push(row);return row; },
    scrollThread(){}, actionRow(){return node();}, credentials(){return state.session?{username:'test',key:'session-only'}:{};},
    currentConversation(){return state.conversations[state.activeId];}, showWelcome(){}, renderConversations(){},
    renderFollowups(){}, renderAccount(){}, loadWallet:async()=>{}, requireAccount(){throw Error('login required');},
    api:async(path)=>path.endsWith('/create')?{conversation:{id:'server-conversation'}}:{success:true},
  };
  vm.createContext(state);vm.runInContext(live+send+regen+stop,state);return state;
}
const encoder = new TextEncoder();
const frame = 'event: delta\r\ndata: {"text":"Xin chào 323"}\r\n\r\nevent: done\r\ndata: {"success":true}\r\n\r\n';
function response(text=frame) {
 const bytes=encoder.encode(text);let i=0;
 return new Response(new ReadableStream({pull(controller){if(i===bytes.length)controller.close();else controller.enqueue(bytes.slice(i,i+=1));}}),{headers:{'Content-Type':'text/event-stream'}});
}
async function waitDone(c) { for(let n=0;n<100&&c.streaming;n++) await new Promise(r=>setTimeout(r,2));assert.equal(c.streaming,null); }
(async()=>{
 let c=context(async()=>response());
 c.sendMessage('17 times 19');assert.ok(c.streaming,'request must lock before waiting for network');
 c.sendMessage('duplicate');assert.equal(c.conversations[0].messages.length,1);
 await waitDone(c);assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/cloud/chat');
 assert.equal(calls[0].payload.history.length,0,'current question must not be repeated in history');
 assert.equal(calls[0].payload.use_memory,false);assert.equal(c.conversations[0].messages[1].text,'Xin chào 323');
 c.sendMessage('follow up');await waitDone(c);assert.equal(calls[1].payload.history.length,2);
 c.regenerate();await waitDone(c);assert.equal(calls.length,3,'regeneration calls real API');
 assert.equal(calls[2].payload.text,'follow up');
 c=context(async()=>response('event: delta\ndata: {"text":"partial"}\n\n'));
 c.sendMessage('x');await waitDone(c);assert.equal(c.conversations[0].messages.length,1,'truncated result must not be saved as complete');assert.ok(rows.some(r=>r.text?.includes('Kết nối bị ngắt')));
 c=context(async()=>response('event: error\ndata: {"message":"Provider quota"}\n\n'));
 c.sendMessage('x');await waitDone(c);assert.ok(rows.some(r=>r.text==='Provider quota'));
 c=context(async()=>new Response(JSON.stringify({success:false,message:'Please log in'}),{status:401}));
 c.sendMessage('x');await waitDone(c);assert.ok(rows.some(r=>r.text==='Please log in'));
 c=context(async()=>new Response(JSON.stringify({success:true,answer:'Real provider answer'})));
 c.session={username:'test'};c.model={id:'gemini'};c.sendMessage('hello');await waitDone(c);
 assert.equal(calls[0].url,'/api/provider/model');assert.equal(calls[0].payload.provider,'gemini');assert.equal(calls[0].payload.stream,false);
 assert.equal(calls[0].payload.messages.at(-1).content,'hello');assert.equal(c.conversations[0].messages.at(-1).text,'Real provider answer');
 let rejectFetch;
 c=context((url,{signal})=>new Promise((resolve,reject)=>{rejectFetch=reject;signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')));}));
 c.sendMessage('cancel me');const signal=calls[0].signal;c.stopStream();assert.equal(signal.aborted,true);await new Promise(r=>setTimeout(r,5));assert.equal(c.conversations[0].messages.length,1);
 console.log('PASS: live streaming, UTF-8 fragmented frames, history, duplicate submission, regeneration, provider routing, API errors, truncated streams, cancellation');
})().catch(error=>{console.error(error);process.exitCode=1;});
