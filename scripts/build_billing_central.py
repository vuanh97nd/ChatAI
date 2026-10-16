"""Inline the central billing implementation into Dashboard and Wrangler Workers."""
from pathlib import Path
from datetime import datetime
import subprocess

ROOT=Path(__file__).resolve().parents[1]
MARKER='// BEGIN CENTRAL BILLING V1\n'


def integrate(source,fragment):
    if MARKER in source:source=source.split(MARKER)[0]
    if 'async function localBillingAPI(' not in source:
        source=source.replace('async function billingAPI(', 'async function localBillingAPI(')
        source=source.replace('async function billingProvider(', 'async function localBillingProvider(')
        source=source.replace('async function adminBillingTotals(', 'async function localAdminBillingTotals(')
        anchor='async function billingConfig(env){\n'
        if source.count(anchor)!=1:raise ValueError('Unknown billing configuration implementation')
        source=source.replace(anchor,anchor+" if(env.BILLING_CONFIG_OVERRIDE)return env.BILLING_CONFIG_OVERRIDE;\n if(billingTopology(env)?.role==='primary')return billingRemoteConfig(env);\n")
        anchor="   await ensureRuntimeSchema(env.DB);\n"
        if source.count(anchor)!=1:
            anchor="   await ensureSchema(env.DB);\n"
        if source.count(anchor)!=1:raise ValueError('Unknown request router')
        source=source.replace(anchor,anchor+"   if(path===centralBillingPath)return respond(await billingCentralAPI(env,request,body,raw));\n")
        anchor="  if(env.MEMORY_SYNC_PEER&&env.MEMORY_SYNC_KEY)ctx.waitUntil("
        if source.count(anchor)!=1:raise ValueError('Unknown scheduler')
        source=source.replace(anchor,"  if(env.BILLING_ROLE==='primary')ctx.waitUntil(billingScheduledSync(env).catch(()=>console.error('billing_sync_failed')));\n"+anchor)
        source=source.replace("const user=await db.prepare('SELECT * FROM users WHERE username=?').bind(body.target).first();",
                              "const user=env.BILLING_IDENTITIES?.[body.target]||await db.prepare('SELECT * FROM users WHERE username=?').bind(body.target).first();")
        source=source.replace("const user=admin?await db.prepare('SELECT * FROM users WHERE username=?').bind(target).first():actor;",
                              "const user=admin?(env.BILLING_IDENTITIES?.[target]||await db.prepare('SELECT * FROM users WHERE username=?').bind(target).first()):actor;")
    anchor="   if(path===centralBillingPath)return respond(await billingCentralAPI(env,request,body,raw));\n"
    if 'await billingClientSession(env,actor,body)' not in source:
        addition="""   if(path==='/api/account/billing-session'){
    if(request.method!=='POST')return respond(fail('POST required.',405));
    const actor=await auth(env,body.username,body.key);if(!actor)return respond(fail('Đăng nhập lại để thanh toán.',401));
    if(!await throttle(env.DB,actor.username,'billing-session',30))return respond(fail('Vui lòng chờ.',429));
    return respond(await billingClientSession(env,actor,body));
   }
   if(env.BILLING_ROLE==='authority'&&typeof body.billing_session==='string'&&(path.startsWith('/api/billing/')||path.startsWith('/api/admin/billing/')))return respond(await billingDirectClientAPI(env,request,path,body));
"""
        if source.count(anchor)!=1:raise ValueError('Unknown direct billing router')
        source=source.replace(anchor,anchor+addition)
    source=source.replace("const billing=await adminBillingTotals(env,(rows.results||[]).map(u=>u.username));", "const billing=body.billing_direct===true&&env.BILLING_ROLE==='primary'?new Map():await adminBillingTotals(env,(rows.results||[]).map(u=>u.username));")
    source=source.replace("const billing=(await adminBillingTotals(env,[target])).get(target);", "const billing=body.billing_direct===true&&env.BILLING_ROLE==='primary'?null:(await adminBillingTotals(env,[target])).get(target);")
    return source.rstrip()+'\n\n'+MARKER+fragment.rstrip()+'\n'


def main():
    fragment=(ROOT/'server/fragments/billing-central.js').read_text(encoding='utf-8-sig')
    results={}
    for relative in ('server/worker.js','work.js'):
        path=ROOT/relative;source=path.read_text(encoding='utf-8-sig');result=integrate(source,fragment)
        subprocess.run(['node','--input-type=module','--check'],input=result,text=True,encoding='utf-8',check=True,capture_output=True)
        if result!=source:results[relative]=result
    backup=ROOT/'data'/'billing-worker-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for relative,result in results.items():
        path=ROOT/relative;copy=backup/relative
        copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(path.read_bytes())
        path.write_text(result,encoding='utf-8')
    print('Workers prepared and syntax checked:',len(results),'changed. No cloud deployment or real wallet modification.')


if __name__=='__main__':main()
