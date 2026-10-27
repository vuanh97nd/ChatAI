const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(process.argv[2],'utf8');
function element(tag){return{tag,children:[],textContent:'',replaceChildren(){this.children=[];},append(...children){this.children.push(...children);}};}
const document={createElement:element,createTextNode:text=>({tag:'#text',textContent:text})};
const c=vm.createContext({document});
vm.runInContext(source.slice(source.indexOf('function renderRichText('),source.indexOf('\nfunction manageConversation(')),c);
function tags(node){return[node.tag,...node.children?.flatMap(tags)||[]];}
function text(node){return node.textContent+(node.children||[]).map(text).join('');}
test('AI formatting never interprets HTML or script URLs',()=>{
 const target=element('div');c.renderRichText(target,'<img src=x onerror=alert(1)> **bold** [bad](javascript:alert(1))');
 assert.ok(!tags(target).includes('img'));assert.ok(!tags(target).includes('a'));assert.ok(tags(target).includes('strong'));assert.match(text(target),/<img src=x/);
});
test('headings and fenced code remain readable and preserve literal HTML',()=>{
 const target=element('div');c.renderRichText(target,'## Heading\n\n```html\n<script>alert(1)</script>\n```');
 assert.ok(tags(target).includes('h3'));assert.ok(tags(target).includes('pre'));assert.ok(!tags(target).includes('script'));assert.match(text(target),/<script>alert\(1\)<\/script>/);
});
