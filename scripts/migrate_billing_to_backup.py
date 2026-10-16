"""Explicit admin-led transfer using the locally saved main-server session."""
import argparse
from pathlib import Path
import sys
from uuid import UUID


def main():
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    parser=argparse.ArgumentParser(description='Transfer frozen billing ledger to backup; never print credentials.')
    parser.add_argument('--request-id',type=UUID)
    parser.add_argument('--confirm',action='store_true')
    parser.add_argument('--check',action='store_true',help='Check link/configuration only; do not transfer a ledger.')
    args=parser.parse_args()
    if not args.check and (not args.confirm or not args.request_id):parser.error('Read server/BILLING-CENTRAL.md, back up both databases, freeze both Workers, then pass --request-id and --confirm.')
    from assistant.accounts import load_login,request_account
    session=load_login()
    if not session or session.get('endpoint','').rstrip('/')!='https://chatai.anhvn53.workers.dev':
        raise SystemExit('Log in to the main server in Chat AI and enable Remember login first.')
    if session.get('username','').lower()!='admin' and session.get('role')!='system':
        raise SystemExit('A saved main-server admin session is required.')
    try:
        body={'username':session['username'],'key':session['key']}
        if not args.check:body.update(confirm='MIGRATE_BILLING_TO_BACKUP',request_id=str(args.request_id))
        result=request_account(session['endpoint'],'/api/admin/billing/'+('central-check' if args.check else 'central-migration'),body,timeout=60)
    except Exception as error:
        # API helper sanitizes errors, but do not print arbitrary response bodies here.
        code=getattr(error,'code',None)
        message=str(error)
        if session.get('key'):message=message.replace(session['key'],'[HIDDEN]')
        raise SystemExit('Migration not confirmed. Code: '+str(code or type(error).__name__)+'. '+message+'. Keep freeze and source data; retry the same request-id after checking Workers Logs.') from None
    finally:
        session.clear()
    if args.check:
        print('Connected:',bool(result.get('connected')))
        for name,value in result.get('checks',{}).items():print(name,':',value)
        print('Peer HTTP:',result.get('peer_http_status'))
        print('Cause:',result.get('cause'))
        if result.get('connection_detail'):print('Connection detail:',result['connection_detail'])
        print('No balances or orders were transferred.')
        return
    print(result.get('message','Migration response received.'))
    print('Already imported:',bool(result.get('already_imported')))
    if isinstance(result.get('counts'),dict):
        for table,count in result['counts'].items():print(table,':',count)
    print('Verify balances/history on backup before disabling freeze. No source tables were deleted.')


if __name__=='__main__':main()
