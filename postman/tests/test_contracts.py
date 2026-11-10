import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import manage
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = manage.load(manage.ROOT/'specs/rest.openapi.json')
        cls.registry = Registry().with_resource('urn:rest', Resource.from_contents(cls.spec, default_specification=DRAFT202012))

    def check(self, schema, value):
        Draft202012Validator({'$ref':'urn:rest#/components/schemas/'+schema}, registry=self.registry).validate(value)

    def test_domain_confidence_and_legacy_bulk(self):
        self.check('DomainTechnology', {'confidence':0.8})
        self.check('BulkDomainTechnology', {})
        for value in ({}, {'confidence':1.1}, {'confidence':'0.8'}):
            with self.assertRaises(ValidationError):self.check('DomainTechnology', value)

    def test_registration_strings_preserve_zeros(self):
        self.check('DomainCompanyRegistration', {'number':'001234'})
        with self.assertRaises(ValidationError):self.check('DomainCompanyRegistration', {'number':1234})

    def test_pagination_and_nullable_lists(self):
        self.check('ListResult', {'FI':1.5,'SKU':None})
        with self.assertRaises(ValidationError):self.check('ListResult', {'SKU':'unknown'})
        fixtures=manage.load(manage.ROOT/'contracts/fixtures.json')
        value=copy.deepcopy(fixtures['relationship']['value'])
        value['page']=0
        with self.assertRaises(ValidationError):self.check('RelationshipsApiResponse',value)

    def test_scanner_rejects_nested_secrets_without_echo(self):
        fake='PMAK'+'-'+'x'*40
        values=[{'key':'KEY','value':'not-a-placeholder'}, {'access_token':'private-value'},
                {'body':json.dumps({'device_code':'private-value'})},
                'https://example.com/?'+'KEY='+'private-value', fake]
        for value in values:
            with self.assertRaises(manage.CheckError) as caught:manage.scan(value)
            self.assertNotIn('private-value',str(caught.exception))
            self.assertNotIn(fake,str(caught.exception))
        with patch.dict(os.environ,{'POSTMAN_API_KEY':'private-environment-value'}):
            with self.assertRaises(manage.CheckError):manage.scan('private-environment-value')

    def test_scanner_accepts_placeholders(self):
        manage.scan({'key':'Authorization','value':'Bearer {{ACCESS_TOKEN}}'})
        manage.scan({'body':json.dumps({'device_code':'{{DEVICE_CODE}}'})})
        manage.scan('`https://example.com/?KEY=YOUR_KEY`')

    def test_credential_destination_and_redirects(self):
        with self.assertRaises(manage.CheckError):manage.request('https://example.com/',key='test')
        with self.assertRaises(manage.CheckError):manage.request('https://api.getpostman.com.evil.test/',key='test')
        with self.assertRaises(manage.CheckError):manage.NoRedirect().redirect_request(None,None,None,None,None,None)

    def test_no_secret_no_mutation(self):
        with patch.object(manage,'validate'), patch.dict(os.environ,{},clear=True), patch.object(manage,'api') as remote:
            with self.assertRaises(manage.CheckError):manage.sync()
            remote.assert_not_called()

    def test_sync_verifies_changed_spec_and_skips_matching(self):
        manifest={'collections':[], 'specs':[{'id':'example','file':'test.json'}]}
        desired={'openapi':'3.1.0'}
        def local(path):return manifest if Path(path).name=='manifest.json' else desired
        for same in (True,False):
            answers=[{'workspace':{'collections':[]}}, {'content':json.dumps(desired if same else {})}]
            if not same:answers += [{}, {'content':json.dumps(desired)}]
            with patch.object(manage,'validate'), patch.object(manage,'load',side_effect=local), patch.dict(os.environ,{'POSTMAN_API_KEY':'test'}), patch.object(manage,'api',side_effect=answers) as remote:
                manage.sync()
                self.assertEqual(remote.call_count,2 if same else 4)
                if not same:self.assertEqual(remote.call_args_list[2].args[2],'PATCH')

    def test_domain_version_does_not_confuse_vector_or_trends(self):
        text='/v26/api.json /vector/v99/api.json /trends/v99/api.json /lists13/api.json /rv5/api.json /trustv2/api.json /mcp2/api.json'
        self.assertEqual(manage.versions(text)['domain'],'/v26/api.')


if __name__=='__main__':unittest.main()
