const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'..','web-demo','app.js'),'utf8');
const c=vm.createContext({});
{const a=src.indexOf('const LATEX_SYMBOLS'),b=src.indexOf('function tableCopyButton(');vm.runInContext(src.slice(a,b).replace(/^const /gm,'var '),c);}

test('LaTeX in table cells becomes Excel-safe Unicode',()=>{
 assert.equal(c.latexToText('$\\phi = 30^\\circ$'),'φ = 30°');
 assert.equal(c.latexToText('$x^2 + y_1$'),'x² + y₁');
 assert.equal(c.latexToText('$\\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$'),'(-b ± √(b²-4ac))/(2a)');
 assert.equal(c.latexToText('\\(\\Delta \\le 0\\)'),'Δ ≤ 0');
 assert.equal(c.latexToText('$\\gamma = 18\\,\\text{kN/m}^3$'),'γ = 18 kN/m³');
 assert.equal(c.latexToText('**Sét pha**'),'Sét pha');
 assert.equal(c.latexToText('12,5'),'12,5');
});

// Inline-math detection inside the renderer: $…$ with math becomes \(…\), prices stay.
{const a=src.indexOf('const inlineDollar='),b=src.indexOf('\n',a);vm.runInContext(src.slice(a,b).replace(/^\s*const /,'var '),c);}
test('inline $…$ is recognised as math, prices are left alone',()=>{
 assert.equal(c.inlineDollar('Phương trình $ ax^2 + bx + c = 0 $ (với $ a \\neq 0 $).'),'Phương trình \\(ax^2 + bx + c = 0\\) (với \\(a \\neq 0\\)).');
 assert.equal(c.inlineDollar('Nếu $\\Delta > 0$: 2 nghiệm'),'Nếu \\(\\Delta > 0\\): 2 nghiệm');
 assert.equal(c.inlineDollar('biến $x$ và $y$'),'biến \\(x\\) và \\(y\\)');
 assert.equal(c.inlineDollar('Giá $5 và $10 mỗi cái'),'Giá $5 và $10 mỗi cái');
 assert.equal(c.inlineDollar('Tổng $1000$'),'Tổng $1000$');
});
