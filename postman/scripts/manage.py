"""Validate and sync public Postman artifacts without running BuiltWith lookups."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = 'ebe165e3-135a-46e8-b0df-5a9b475dadc0'
DOC_URL = 'https://api.builtwith.com/llms.txt'
PUBLIC_SPECS = {'x402.openapi.json':'https://api.builtwith.com/openapi.json','billing.openapi.json':'https://api.builtwith.com/mppx/openapi.json'}
FAMILIES = {'domain':r'(?<!trends)(?<!vector)/v\d+/api\.', 'lists':r'/lists\d+/api\.', 'relationships':r'/rv\d+/api\.', 'trust':r'/trustv\d+/api\.', 'registry':r'/mcp\d+/api\.'}
TOKEN = re.compile(r'PMAK-[A-Za-z0-9-]{15,}|npm_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bbw-[0-9a-f]{24,}\b',re.I)
SENSITIVE = {'key','api_key','apikey','access_token','refresh_token','device_code','authorization','x-api-key','x-builtwith-api-key','token','secret','password','cookie','set-cookie','payment-signature','idempotency-key'}
PLACEHOLDER = re.compile(r'^(?:\{\{[^{}]+\}\}|\$\{[^{}]+\}|\$(?:\{\{|env:)[^\r\n]+|(?:YOUR|EXAMPLE|TEST|REDACTED|PLACEHOLDER)[_ -][A-Z0-9_ -]+|\[(?:your[-_ ]key|redacted)\]|<[^<>]+>|bw-\.\.\.)$',re.I)

class CheckError(Exception): pass

def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def dump(path,obj): Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def is_placeholder(value):
    if value in ('',None):return True
    value=str(value).strip()
    value=re.sub(r'^(?:API|Bearer|Payment)\s+','',value,flags=re.I)
    return bool(PLACEHOLDER.fullmatch(value))

def scan(value, label='artifact', declarations=False):
    """Fail with a location only; never echo the offending value."""
    if isinstance(value,dict):
        name=str(value.get('key',value.get('name',''))).lower()
        if name in SENSITIVE and 'value' in value and not is_placeholder(value['value']):raise CheckError(label+': populated credential field')
        for k,v in value.items():
            metadata_key = k=='key' and 'value' in value
            if not declarations and not metadata_key and k.lower() in SENSITIVE and isinstance(v,str) and not is_placeholder(v):raise CheckError(label+': populated credential property')
            scan(v,label+'/'+k,declarations)
    elif isinstance(value,list):
        for i,v in enumerate(value):scan(v,label+'/'+str(i),declarations)
    elif isinstance(value,str):
        if TOKEN.search(value):raise CheckError(label+': credential pattern')
        for secret in (os.environ.get('POSTMAN_API_KEY',''),os.environ.get('BUILTWITH_API_KEY','')):
            if len(secret)>8 and secret in value:raise CheckError(label+': environment credential present')
        decoded=urllib.parse.unquote(value)
        for match in re.finditer(r'(?i)[?&](?:KEY|api_key|access_token|token)=([^&\s"<>`\)]+)',decoded):
            if not is_placeholder(match[1]):raise CheckError(label+': populated URL credential')
        # JSON bodies and example responses may be JSON encoded inside JSON.
        if value.lstrip().startswith(('{','[')):
            try:nested=json.loads(value)
            except (ValueError,TypeError):pass
            else:scan(nested,label+'/embedded-json')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise CheckError('HTTP redirect refused')

def request(url,method='GET',body=None,key=None):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.username or parsed.password:raise CheckError('Unsafe request URL')
    if key and parsed.netloc!='api.getpostman.com':raise CheckError('Credential destination refused')
    if not key and url not in {DOC_URL,*PUBLIC_SPECS.values()}:raise CheckError('Unapproved public source URL')
    headers={'Content-Type':'application/json'}
    if key:headers['X-Api-Key']=key
    payload=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else None
    req=urllib.request.Request(url,headers=headers,data=payload,method=method)
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=90) as response:return response.read().decode('utf-8-sig')
    except urllib.error.HTTPError as exc:raise CheckError(f'Remote request failed (HTTP {exc.code}); response omitted to protect credentials') from None
    except (urllib.error.URLError,TimeoutError):raise CheckError('Remote request failed; connection details omitted') from None

def api(path,key,method='GET',body=None):
    if not re.fullmatch(r'(?:collections/[\w-]+|workspaces/[\w-]+|specs/[\w-]+/files/[\w.-]+)',path):raise CheckError('Postman resource path refused')
    return json.loads(request('https://api.getpostman.com/'+path,method,body,key))

def items(collection):
    for item in collection.get('item',[]):
        if 'request' in item:yield item
        yield from items(item)

def canonical(v):
    if isinstance(v,dict):
        excluded={'id','_postman_id','uid','createdAt','updatedAt','lastUpdatedBy','owner'}
        return {k:(urllib.parse.unquote(x) if k=='raw' and isinstance(x,str) and x.startswith('https://') else canonical(x)) for k,x in v.items() if k not in excluded}
    if isinstance(v,list):
        if v and all(isinstance(x,dict) and 'name' in x and ('request' in x or 'item' in x) for x in v):v=sorted(v,key=lambda x:x['name'])
        return [canonical(x) for x in v]
    return v

def contains(actual,expected):
    if isinstance(expected,dict):return isinstance(actual,dict) and all((k not in actual and (v in ('',[],{}) or (k=='disabled' and v is False))) or (k in actual and contains(actual[k],v)) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(contains(a,b) for a,b in zip(actual,expected))
    return actual==expected

def versions(text):
    found={}
    for family,pattern in FAMILIES.items():
        matches=set(re.findall(pattern,text))
        if not matches:raise CheckError('Missing current endpoint family: '+family)
        # Docs deliberately mention older versions in prose; only /.../api. paths count.
        nums=[(int(re.search(r'\d+',m)[0]),m) for m in matches]
        found[family]=max(nums)[1]
    return found

def validate(online=False,caller=None,repo=None):
    from jsonschema import Draft4Validator,Draft7Validator,Draft202012Validator
    from referencing import Registry,Resource
    from openapi_spec_validator import validate as validate_openapi
    manifest=load(ROOT/'manifest.json')
    if manifest['workspaceId']!=WORKSPACE:raise CheckError('Workspace manifest mismatch')
    # Scan only public artifact trees plus automation files; do not inspect environment files.
    for directory in ('collections','specs','contracts','scripts','tests'):
        for f in (ROOT/directory).rglob('*'):
            if not f.is_file() or '__pycache__' in f.parts:continue
            text=f.read_text(encoding='utf-8-sig')
            scan(load(f) if f.suffix=='.json' else text,str(f.relative_to(ROOT)),f.name in ('sdk-models.json','server-models.json'))
    for f in (ROOT.parent/'.github/workflows').glob('*.yml'):scan(f.read_text(encoding='utf-8'),f.name)
    collection_validator=Draft4Validator(load(ROOT/'schemas/collection-v2.1.json'))
    for entry in manifest['collections']:
        c=load(ROOT/'collections'/entry['file']);collection_validator.validate(c)
        for item in items(c):
            u=item['request']['url']
            actual=urllib.parse.parse_qsl(urllib.parse.urlsplit(u['raw']).query,keep_blank_values=True)
            expected=[(p['key'],p.get('value','')) for p in u.get('query',[]) if not p.get('disabled')]
            if actual!=expected:raise CheckError(entry['file']+': structured/raw URL mismatch')
    for entry in manifest['specs']:
        spec=load(ROOT/'specs'/entry['file'])
        if 'openapi' in spec:validate_openapi(spec)
        else:Draft7Validator(load(ROOT/'schemas/asyncapi-2.6.json')).validate(spec)
    rest=load(ROOT/'specs/rest.openapi.json')
    registry=Registry().with_resource('urn:builtwith:rest',Resource.from_contents(rest,default_specification=__import__('referencing.jsonschema',fromlist=['DRAFT202012']).DRAFT202012))
    for name,fixture in load(ROOT/'contracts/fixtures.json').items():
        Draft202012Validator({'$ref':'urn:builtwith:rest#/components/schemas/'+fixture['schema']},registry=registry).validate(fixture['value'])
    # Rebuilding must not alter reviewed output.
    from refine_spec import build
    if build()!=rest:raise CheckError('REST spec is out of date; run scripts/refine_spec.py')
    contract=load(ROOT/'contracts/endpoints.json')
    all_urls='\n'.join(i['request']['url']['raw'] for e in manifest['collections'] for i in items(load(ROOT/'collections'/e['file'])))
    for family,expected in contract['versions'].items():
        seen=set(re.findall(FAMILIES[family],all_urls+'\n'+'\n'.join(rest['paths'])))
        if seen!={expected}:raise CheckError('Endpoint drift in committed assets: '+family)
    if online:
        live=versions(request(DOC_URL))
        if live!=contract['versions']:raise CheckError('Public API versions changed; update endpoint contracts and collections before release')
        for file,url in PUBLIC_SPECS.items():
            published=json.loads(request(url));scan(published,'public spec')
            if published!=load(ROOT/'specs'/file):raise CheckError('Published OpenAPI changed: '+file)
    if caller:
        paths=contract['releaseSources'].get(repo)
        if not paths:raise CheckError('No release source mapping for caller repository')
        for file in paths:
            source=Path(caller)/file
            if not source.is_file():raise CheckError('Release endpoint source missing: '+file)
            text=source.read_text(encoding='utf-8-sig')
            text += '\n'+'\n'.join('/'+m for m in re.findall(r'["\']((?:v\d+|lists\d+|rv\d+|trustv\d+|mcp\d+)/api\.)',text))
            if repo=='builtwith/builtwith-node-api':
                text += '\n'+'\n'.join('/'+m+'/api.' for m in re.findall(r'constructBuiltWithURL\("([a-z0-9]+)"',text))
            for family,pattern in FAMILIES.items():
                found_paths=re.findall(pattern,text)
                if not found_paths and repo!='builtwith/builtwith-ai-sdk':raise CheckError('Missing release endpoint family: '+family)
                for found in found_paths:
                    if found!=contract['versions'][family]:raise CheckError('Release uses outdated endpoint: '+family+' in '+file)
        if repo=='builtwith/builtwith-csharp-api':
            for file,digest in load(ROOT/'contracts/sdk-models.json')['files'].items():
                source=Path(caller)/file
                if not source.exists() or hashlib.sha256(source.read_text(encoding='utf-8-sig').replace('\r\n','\n').encode()).hexdigest()!=digest:raise CheckError('C# model changed; review Postman contracts: '+file)
    print('PASS: specs, fixtures, collections, endpoint versions and credential scan'+(' (including public source drift)' if online else ''))

def sync():
    validate(online=True)
    key=os.environ.get('POSTMAN_API_KEY','')
    if not key:raise CheckError('POSTMAN_API_KEY secret is not configured')
    manifest=load(ROOT/'manifest.json')
    workspace=api('workspaces/'+WORKSPACE,key)['workspace']
    known={c['uid'] for c in workspace.get('collections',[])}
    if not all(e['uid'] in known for e in manifest['collections']):raise CheckError('Collection does not belong to the expected workspace')
    # Validate every payload before the first mutation; IDs come only from the reviewed manifest.
    prepared=[]
    for entry in manifest['collections']:
        value=load(ROOT/'collections'/entry['file']);scan(value,entry['file']);prepared.append(('collection',entry,value))
    for entry in manifest['specs']:
        value=load(ROOT/'specs'/entry['file']);scan(value,entry['file']);prepared.append(('spec',entry,value))
    changed=0
    for kind,entry,value in prepared:
        path='collections/'+entry['uid'] if kind=='collection' else 'specs/'+entry['id']+'/files/'+entry['file']
        remote=api(path,key)
        actual=remote['collection'] if kind=='collection' else json.loads(remote['content'])
        equal=contains(canonical(actual),canonical(value)) if kind=='collection' else actual==value
        if equal:continue
        # No lookup requests are executed; only Postman definitions are uploaded.
        api(path,key,'PUT' if kind=='collection' else 'PATCH',{'collection':value} if kind=='collection' else {'content':json.dumps(value,ensure_ascii=False,indent=2)+'\n'})
        saved=api(path,key)
        actual=saved['collection'] if kind=='collection' else json.loads(saved['content'])
        if not (contains(canonical(actual),canonical(value)) if kind=='collection' else actual==value):raise CheckError('Postman readback mismatch: '+entry['file'])
        changed+=1
        print('Verified',entry['file'])
    print('Sync complete:',changed,'changed resources; all remaining resources already matched.')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['check','sync'])
    parser.add_argument('--online',action='store_true')
    parser.add_argument('--caller');parser.add_argument('--repo')
    args=parser.parse_args()
    try:
        if args.command=='sync':sync()
        else:validate(args.online,args.caller,args.repo)
    except CheckError as exc:print('ERROR:',str(exc),file=sys.stderr);return 1
    except Exception as exc:
        # Validator exceptions embed offending values. Never send them to CI logs.
        print('ERROR: validation/operation failed ('+type(exc).__name__+'); inspect local artifacts without logging credentials.',file=sys.stderr);return 1
    return 0

if __name__=='__main__':sys.exit(main())
