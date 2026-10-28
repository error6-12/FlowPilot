const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path').join(process.cwd(), 'web', 'templates') + require('path').sep;
const html=fs.readFileSync(path+'index.html','utf8');
const script=html.split('<script>')[1].split('</script>')[0];
new vm.Script(script);
const context=vm.createContext({});
vm.runInContext(script.slice(script.indexOf('    function escapeHtml'),script.indexOf('    function formatWorkflowDate')),context);
assert.match(context.formatMessageText('**重点**'),/<strong>重点<\/strong>/);
assert.match(context.formatMessageText('# 标题\n- 条目'),/<strong>标题/);
assert.match(context.formatMessageText('| A | B |\n| --- | --- |\n| 1 | 2 |'),/<table>/);
assert(!context.formatMessageText('<img src=x onerror=alert(1)>').includes('<img'));
assert(!context.formatMessageText('**<script>x</script>**').includes('<script>'));
for(const fence of ['```','```text']) {
 const rendered=context.formatMessageText(fence+'\n员工提交 → 审批\n<script>alert(1)</script>\n```');
 assert.match(rendered,/<pre><code>/);
 assert(!rendered.includes('```'));
 assert(!rendered.includes('<script>'));
}
const knowledge=fs.readFileSync(path+'knowledge_management.html','utf8').split('<script>')[1].split('</script>')[0];
new vm.Script(knowledge);
vm.runInContext(knowledge.slice(0,knowledge.indexOf('        let knowledgeData')),context);
assert.match(context.knowledgePreview('```\n员工提交 → 审批\n```'),/<pre><code>员工提交/);
const sources=context.splitReplySources('回答\n**引用来源：**\n- policy.md');
assert.equal(sources.answer,'回答');
assert.equal(sources.sources[0],'policy.md');
const cache=new Map();
context.sessionStorage={setItem:(k,v)=>cache.set(k,v),getItem:k=>cache.get(k),removeItem:k=>cache.delete(k)};
context.console=console;
context.chatBox={querySelectorAll:()=>[{dataset:{sender:'user',raw:'我要请假'}},{dataset:{sender:'bot',raw:'[REPLY]请提供日期'}}]};
vm.runInContext("let conversationId='test-session'; const historyKey = () => `flowpilot.history.${conversationId}`; let restoringHistory=false;",context);
vm.runInContext(script.slice(script.indexOf('    function saveHistory'),script.indexOf('    function addMessage')),context);
context.saveHistory();
assert.equal(JSON.parse(cache.get('flowpilot.history.test-session')).length,2);
context.chatBox={replaceChildren:()=>{},lastElementChild:{querySelector:()=>({})}};
context.welcomeTemplate={cloneNode:()=>({})};
const restored=[];
context.addMessage=(text,sender)=>restored.push({text,sender});
context.updateLastBotMessage=()=>{};
context.hydrateWorkflowCard=()=>{};
vm.runInContext(script.slice(script.indexOf('    try {\n        const saved = JSON.parse'),script.indexOf('    // 添加回车键')),context);
assert.equal(restored.length,2);
assert.equal(restored[1].text,'[REPLY]请提供日期');
const ops=fs.readFileSync(path+'operations_dashboard.html','utf8').split('<script>')[1].split('</script>')[0];
new vm.Script(ops);
vm.runInContext(ops.slice(0,ops.indexOf('    async function json')),context);
assert.match(context.table(['错误'],[],'暂无错误'),/暂无错误/);
assert(!context.table(['错误'],[],'暂无错误').includes('暂无运行记录'));
// Exercise the actual reply-envelope renderer, not just Markdown in isolation.
const messageNode={dataset:{sender:'bot',raw:''}};
const bubble={innerHTML:'',closest:()=>messageNode};
context.lastBotBubble=bubble;
context.chatBox={querySelectorAll:()=>[messageNode],scrollTo:()=>{},scrollHeight:0};
context.requestAnimationFrame=callback=>callback();
vm.runInContext(script.slice(script.indexOf('    function updateLastBotMessage'),script.indexOf('    chatForm.onsubmit')),context);
for (const fence of ['```','```text']) {
    const raw='[THOUGHT][归类机器人]咨询任务[REPLY][咨询机器人]'+fence+'\n员工提交 → 主管审批\n<script>alert(1)</script>\n```\n**引用来源：**\n- hr_policy/leave_policy.md';
    // Every boundary, including partial agent labels and partial fences.
    for (let i=1;i<=raw.length;i++) context.updateLastBotMessage(raw.slice(0,i));
    assert.match(bubble.innerHTML,/<pre><code>员工提交 → 主管审批\n&lt;script&gt;/);
    assert(!bubble.innerHTML.includes('```'));
    assert(!bubble.innerHTML.includes('[咨询机器人]'));
    assert(!bubble.innerHTML.includes('<script>'));
    assert.match(bubble.innerHTML,/hr_policy\/leave_policy.md/);
    const saved=JSON.parse(cache.get('flowpilot.history.test-session'));
    assert.equal(saved[0].text,raw);
    bubble.innerHTML='';
    // Restore through the real history loop and real reply renderer.
    context.chatBox.replaceChildren=()=>{};
    context.chatBox.lastElementChild={querySelector:()=>bubble};
    context.addMessage=(text,sender)=>{messageNode.dataset={sender,raw:text};};
    vm.runInContext(script.slice(script.indexOf('    try {\n        const saved = JSON.parse'),script.indexOf('    // 添加回车键')),context);
    assert.match(bubble.innerHTML,/<pre><code>员工提交 → 主管审批/);
    assert(!bubble.innerHTML.includes('```'));
}
context.updateLastBotMessage('[REPLY][咨询机器人]```\n尚未闭合\n<b>原样文本</b>');
assert.match(bubble.innerHTML,/<pre><code>尚未闭合\n&lt;b&gt;/);
// Bootstrap two tabs against shared localStorage. Explicit new-session must
// not delete old history or change the other tab's ID after refresh.
const sharedLocal=new Map([['conversation_id','original']]);
const tabA=new Map([['flowpilot.history.original','old messages']]);
const tabB=new Map(); let uuids=0;
function bootstrap(tab,search) {
    const storage=map=>({getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v)});
    const location={search,pathname:'/',hash:''};
    const window={location,history:{replaceState:(a,b,url)=>{location.search=new URL(url,'http://localhost').search;}}};
    const ctx=vm.createContext({window,URLSearchParams,crypto:{randomUUID:()=>`new-${++uuids}`},sessionStorage:storage(tab),localStorage:storage(sharedLocal)});
    vm.runInContext(script.slice(script.indexOf('    const sessionParams'),script.indexOf('    const welcomeTemplate')),ctx);
    return {id:vm.runInContext('conversationId',ctx),search:location.search};
}
assert.equal(bootstrap(tabA,'?v=flowpilot-2').id,'original');
const independent=bootstrap(tabB,'?new_session=1');
assert.notEqual(independent.id,'original');
assert.equal(bootstrap(tabA,'?v=flowpilot-2').id,'original');
assert.equal(bootstrap(tabB,independent.search).id,independent.id);
assert.equal(tabA.get('flowpilot.history.original'),'old messages');
console.log('Frontend: streaming Markdown, history, analytics and independent new-session/refresh preservation passed');
