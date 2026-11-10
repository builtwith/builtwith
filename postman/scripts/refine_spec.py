"""Rebuild wire models from reviewed SDK/server declarations (no credentials/network)."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))

def ref(name):
    return {'$ref': '#/components/schemas/' + name}

def array(name):
    return {'type': 'array', 'items': ref(name)}

def object_schema(properties):
    return {'type': 'object', 'properties': properties, 'additionalProperties': True}

def build():
    spec = read('specs/rest.openapi.json')
    sdk = read('contracts/sdk-models.json')['models']
    server = read('contracts/server-models.json')
    models = {**sdk, **{n: v['properties'] for n, v in server.items()}}
    def convert(t):
        nullable = t.endswith('?')
        t = t.rstrip('?')
        if t.endswith('[]'): s = {'type': 'array', 'items': convert(t[:-2])}
        elif t.startswith('List<'): s = {'type': 'array', 'items': convert(t[5:-1])}
        elif t.startswith('Dictionary<string,'): s = {'type': 'object', 'additionalProperties': convert(t[18:-1])}
        elif t in ('string', 'DateTime'): s = {'type': 'string', **({'format': 'date-time'} if t == 'DateTime' else {})}
        elif t in ('int', 'long'): s = {'type': 'integer', 'format': 'int64' if t == 'long' else 'int32'}
        elif t in ('double', 'decimal', 'float'): s = {'type': 'number'}
        elif t == 'bool': s = {'type': 'boolean'}
        elif t in ('object', 'System.Text.Json.JsonElement'):
            return {'description': 'Arbitrary JSON supplied by the API; its shape depends on the operation.'}
        else:
            if t not in models: raise ValueError('Unknown contract type: ' + t)
            s = ref(t)
        return {'anyOf': [s, {'type': 'null'}]} if nullable else s
    schemas = {n: object_schema({p: convert(t) for p, t in props.items()}) for n, props in models.items()}
    for n in schemas:
        schemas[n]['description'] = ('Reviewed server wire model: ' + server[n]['source'] + '#' + server[n]['class']) if n in server else 'Reviewed BuiltWith C# SDK model: ' + n
    schemas['DomainApiResponse']['properties']['Errors'] = array('ApiError')
    schemas['DomainApiResponse']['properties']['Trust'] = array('DomainTrust')
    schemas['DomainTechnology']['properties']['confidence'] = {'type': 'number', 'minimum': 0, 'maximum': 1, 'description': 'v26 confidence; retained even when text fields are hidden.'}
    schemas['DomainTechnology']['required'] = ['confidence']
    # Bulk remains v23: clone its Domain graph without imposing v26 confidence.
    domain_names = [n for n in schemas if n.startswith('Domain')]
    for n in domain_names:
        raw = json.dumps(schemas[n])
        for target in domain_names:
            raw = raw.replace('#/components/schemas/'+target+'"', '#/components/schemas/Bulk'+target+'"')
        schemas['Bulk'+n] = json.loads(raw)
    schemas['BulkDomainTechnology'].pop('required', None)
    schemas['DomainCompanyRegistration']['properties']['number'] = {'type': 'string', 'description': 'Registration numbers remain strings to preserve leading zeros.'}
    schemas['RelationshipsApiResponse']['properties']['page']['minimum'] = 1
    schemas['RelationshipsApiResponse']['properties']['next_page'].update(minimum=0, description='Use as PAGE while more_results is true; zero means finished.')
    schemas['RelationshipsApiResponse']['properties']['max_per_page']['const'] = 1000
    schemas['RelationshipsApiResponse']['required'] = ['Relationships','Errors','results','max_per_page','page','next_page','more_results']
    schemas['TrustAssessment']['properties']['TrustLevel'] = {'type':'string','enum':['Unverified','RestrictedContent','HighRisk','Caution','VerificationRecommended','Neutral','Trusted']}
    # Ask uses the list result attributes but omits LOS (server ask/v1 inherits list/v12).
    schemas['AskResult'] = copy.deepcopy(schemas['ListResult'])
    schemas['AskResult']['properties'].pop('LOS', None)
    schemas['AskResult']['description'] = 'Ask result attributes from the Lists model; Ask omits LOS.'
    schemas['ApiError']['properties']['Lookup'] = {'type':['string','null']}
    schemas['McpRegistryV2Endpoint']['properties']['Overview'] = {'type':['object','null'],'additionalProperties':True,'description':'Full remote MCP discovery object, including instructions, protocolVersion, serverInfo and capabilities. Extensions are preserved.'}
    schemas['TagMatch']['properties']['First'] = {'type':'string','format':'date-time'}
    schemas['TagMatch']['properties']['Last'] = {'type':'string','format':'date-time'}
    schemas['TagType'] = object_schema({'Name':{'type':'string'},'Abbreviation':{'type':'string'}})
    schemas['DomainCategory'] = object_schema({'Id':{'type':'string'},'Name':{'type':'string'},'SubCategories':{'type':'array','items':object_schema({'Id':{'type':'string'},'Name':{'type':'string'}})}})
    schemas['McpCategory'] = object_schema({'Slug':{'type':'string'},'Label':{'type':'string'},'Count':{'type':'integer','minimum':0}})
    schemas['DatabaseUpdateDates'] = object_schema({n:{'type':'string','pattern':r'^/Date\(-?\d+(?:[+-]\d+)?\)/$','description':'ASP.NET JavaScriptSerializer date, milliseconds since Unix epoch.'} for n in ('FULL','TOPSITE')})
    roots = {
        'Domain_APIResponse':ref('DomainApiResponse'), 'Lists_APIResponse':ref('ListsApiResponse'),
        'Relationships_APIResponse':ref('RelationshipsApiResponse'), 'Change_APIResponse':ref('ChangeApiResponse'),
        'Trust_APIResponse':ref('TrustApiResponse'), 'Free_APIResponse':ref('FreeApiResponse'),
        'Company_to_URL_APIResponse':array('CompanyToUrlResult'), 'Keywords_APIResponse':ref('KeywordsApiResponse'),
        'Keyword_Search_APIResponse':ref('KeywordSearchResponse'), 'Product_APIResponse':ref('ProductApiResponse'),
        'Recommendations_APIResponse':array('RecommendationResult'), 'Redirects_APIResponse':ref('RedirectsApiResponse'),
        'Trends_APIResponse':ref('TrendsApiResponse'), 'Vector_Search_APIResponse':ref('VectorSearchResponse'),
        'VAT_APIResponse':array('VatApiResult'), 'VAT_Types_APIResponse':array('VatTypeResult'),
        'MCP_Registry_APIResponse':array('McpRegistryV2Result'), 'MCP_Categories_APIResponse':array('McpCategory'),
        'Ask_APIResponse':ref('AskApiResponse'), 'WhoAmI_APIResponse':ref('WhoAmIResponse'), 'Usage_APIResponse':ref('UsageResponse'),
        'Tags_APIResponse':{'anyOf':[array('TagResult'),array('TagType')]},
        'Social_APIResponse':{'description':'Social reverse-lookup response; fields vary by source network. See the Social collection examples.'},
        'Financial_APIResponse':{'description':'External company/issuer financial records; schemas vary by registry. See the Financial collection examples.'},
        'Useful_CallsResponse':ref('UsageResponse')
    }
    schemas.update(roots)
    spec['components']['schemas'] = schemas
    spec['info']['version'] = '2026.11.10.1'
    spec['info']['description'] = 'Current BuiltWith REST contracts, refined from reviewed server serialization and maintained C# SDK models. Optional fields may be omitted. Response objects allow additional fields for forward compatibility. Financial/social source-specific payloads and remote MCP Overview extensions remain intentionally open. Maintained with the collections at https://github.com/builtwith/builtwith/tree/main/postman.'
    for path, methods in spec['paths'].items():
        for method, op in methods.items():
            if method not in ('get','post'): continue
            for response in op['responses'].values():
                for media in response.get('content',{}).values():
                    media.pop('example',None) # old captured responses aren't authoritative model definitions
            media = op['responses']['200'].get('content',{}).get('application/json')
            if path == '/v26/api.json':media['schema'] = {'anyOf':[ref('DomainApiResponse'),array('DomainCategory'),{'type':'array','items':{'type':'string'}}]}
            if path == '/tag1/api.json':
                media['schema'] = roots['Tags_APIResponse']
                op['security'] = [{'ApiAuthorization':[]},{'QueryKey':[]},{}]
                prefix = 'LOOKUP requires API authentication and returns TagResult[]. TYPES=true is a public index returning TagType[]. '
                if not op['description'].startswith(prefix):op['description'] = prefix + op['description']
            if path == '/v23/domain/bulk' or path == '/v23/domain/bulk/{job_id}/result':
                media['schema'] = ref('BulkDomainApiResponse')
            if path.startswith('/ignoresv1/') or path.startswith('/ignoretldsv1/') or path.startswith('/suffixv1/'):
                if media: media['schema'] = {'type':'array','items':{'type':'string'}}
            if path == '/agent-auth/start':media['schema'] = ref('AgentAuthStartResponse')
            if path == '/agent-auth/token':
                media['schema'] = ref('AgentAuthTokenResponse')
                op['responses']['400']['content']['application/json']['schema'] = ref('AgentAuthTokenResponse')
            if path.startswith('/usagev2/'):
                # Existing DATES sample does not select an alternate response in the current handler.
                op['parameters'] = [p for p in op['parameters'] if p['name']!='DATES']
                if not any(p['name']=='UPDATE' for p in op['parameters']):
                    op['parameters'].append({'name':'UPDATE','in':'query','required':False,'schema':{'type':'boolean'},'description':'true returns public database update dates instead of authenticated usage.'})
                op['security'] = [{'ApiAuthorization':[]},{'QueryKey':[]},{}]
                if media:media['schema'] = {'anyOf':[ref('UsageResponse'),ref('DatabaseUpdateDates')]}
    # Example fixtures contain only synthetic domains and placeholder tokens.
    for name,fixture in read('contracts/fixtures.json').items():
        if 'path' in fixture:
            op=spec['paths'][fixture['path']][fixture.get('method','get')]
            op['responses'][fixture.get('status','200')]['content']['application/json']['example']=fixture['value']
    return spec

if __name__ == '__main__':
    (ROOT/'specs/rest.openapi.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Refined REST schema from reviewed wire contracts.')
