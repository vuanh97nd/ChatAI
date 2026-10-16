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
    return source.rstrip()+'\n\n'+MARKER+fragment.rstrip()+'\n'


def main():
    fragment=(ROOT/'server/fragments/billing-central.js').read_text()
    results={}
    for relative in ('server/worker.js','work.js'):
        path=ROOT/relative;source=path.read_text();result=integrate(source,fragment)
        subprocess.run(['node','--input-type=module','--check'],input=result,text=True,check=True,capture_output=True)
        if result!=source:results[relative]=result
    backup=ROOT/'data'/'billing-worker-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for relative,result in results.items():
        path=ROOT/relative;copy=backup/relative
        copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(path.read_bytes())
        path.write_text(result)
    print('Workers prepared and syntax checked:',len(results),'changed. No cloud deployment or real wallet modification.')


if __name__=='__main__':main()
