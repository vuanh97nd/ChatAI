"""Explicit admin-led transfer using the locally saved main-server session."""
import argparse
from pathlib import Path
import sys
from uuid import UUID


def main():
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    parser=argparse.ArgumentParser(description='Transfer frozen billing ledger to backup; never print credentials.')
    parser.add_argument('--request-id',required=True,type=UUID)
    parser.add_argument('--confirm',action='store_true')
    args=parser.parse_args()
    if not args.confirm:parser.error('Read server/BILLING-CENTRAL.md, back up both databases, freeze both Workers, then pass --confirm.')
    from assistant.accounts import load_login,request_account
    session=load_login()
    if not session or session.get('endpoint','').rstrip('/')!='https://chatai.anhvn53.workers.dev':
        raise SystemExit('Log in to the main server in Chat AI and enable Remember login first.')
    if session.get('username','').lower()!='admin' and session.get('role')!='system':
        raise SystemExit('A saved main-server admin session is required.')
    try:
        result=request_account(session['endpoint'],'/api/admin/billing/central-migration',
            {'username':session['username'],'key':session['key'],'confirm':'MIGRATE_BILLING_TO_BACKUP','request_id':str(args.request_id)},timeout=60)
    except Exception as error:
        # API helper sanitizes errors, but do not print arbitrary response bodies here.
        code=getattr(error,'code',None)
        raise SystemExit('Migration not confirmed. Code: '+str(code or type(error).__name__)+'. Keep freeze and source data; retry the same request-id after checking Workers Logs.') from None
    finally:
        session.clear()
    print(result.get('message','Migration response received.'))
    print('Already imported:',bool(result.get('already_imported')))
    if isinstance(result.get('counts'),dict):
        for table,count in result['counts'].items():print(table,':',count)
    print('Verify balances/history on backup before disabling freeze. No source tables were deleted.')


if __name__=='__main__':main()
