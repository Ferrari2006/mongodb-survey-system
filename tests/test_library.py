"""Stage-two contracts against a real MongoDB; all fixtures stay in a random test DB."""
import unittest
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import test_api as base


class LibraryTests(unittest.TestCase):
    setUpClass = classmethod(base.ApiTests.setUpClass.__func__)
    tearDownClass = classmethod(base.ApiTests.tearDownClass.__func__)
    setUp = base.ApiTests.setUp
    call = base.ApiTests.call
    survey = base.ApiTests.survey

    def library(self, kind='single'):
        bank = self.call('POST', '/api/banks', {'title':'校园常用题','description':'复用题目'}).json
        q = {'title':'你如何评价食堂？','type':kind,'required':True}
        if kind in ('single','multiple'): q['options']=[{'id':'a','label':'满意'},{'id':'b','label':'一般'}]
        if kind=='number': q['validation']={'min':0,'max':10}
        response=self.call('POST','/api/library/questions',{'bank_id':bank['_id'],'question':q})
        assert response.status_code==201,response.json
        return response.json['item']

    def import_to(self, item, qid='q1', version=None):
        s=self.survey()
        r=self.call('POST',f"/api/surveys/{s['_id']}/library-import",{
            'library_id':item['_id'],'version':version or item['current_version'],'question_id':qid,'revision':s['revision']})
        assert r.status_code==200,r.json
        return r.json

    def update(self,item,**kwargs):
        r=self.call('PATCH',f"/api/library/questions/{item['_id']}",{'revision':item['revision'],**kwargs})
        assert r.status_code==200,r.json
        return r.json

    def submit(self,s,answers):
        p=self.call('POST',f"/api/surveys/{s['_id']}/publish",{'revision':s['revision']})
        assert p.status_code==200,p.json
        r=self.call('POST',f"/api/public/surveys/{s['_id']}/responses",{'answers':answers,'request_id':uuid4().hex})
        assert r.status_code==201,r.json
        return p.json

    def other(self):
        client=self.app.test_client();name='u'+uuid4().hex[:12]
        client.post('/api/auth/register',json={'username':name,'password':'Test-only-123'})
        token=client.post('/api/auth/login',json={'username':name,'password':'Test-only-123'}).json['token']
        return name,lambda method,path,body=None:client.open(path,method=method,json=body,headers={'Authorization':'Bearer '+token})

    def test_working_copy_version_branch_and_restore(self):
        item=self.library();first=deepcopy(item['versions'][0]);q=deepcopy(first['question']);q['title']='修改后的题目'
        item=self.update(item,question=q,create_version=False)
        assert len(item['versions'])==1 and item['versions'][0]==first
        assert item['working_copy']['title']==q['title']
        item=self.update(item,create_version=True)
        assert len(item['versions'])==2 and item['versions'][1]['parent_version']==first['id']
        item=self.update(item,question=first['question'],create_version=True,base_version=first['id'])
        assert item['versions'][2]['parent_version']==first['id']
        r=self.call('POST',f"/api/library/questions/{item['_id']}/restore",{'revision':item['revision'],'version':first['id']})
        assert r.status_code==200,r.json
        assert len(r.json['versions'])==4 and r.json['versions'][3]['restored_from']==first['id']
        assert r.json['versions'][0]==first

    def test_published_snapshot_and_old_version_reuse(self):
        item=self.library();old=item['current_version'];s=self.import_to(item)
        published=self.submit(s,{'q1':'a'})
        q=deepcopy(item['working_copy']);q['title']='第二版题目'
        item=self.update(item,question=q,create_version=True)
        original=self.call('GET',f"/api/surveys/{s['_id']}").json
        assert original['questions']==published['questions']
        reused=self.import_to(item,'reuse',old)
        assert reused['questions'][0]['title']==s['questions'][0]['title']
        failed=self.call('POST',f"/api/surveys/{s['_id']}/library-import",{'library_id':item['_id'],'version':old,'question_id':'q2','revision':published['revision']})
        assert failed.status_code==400

    def test_share_read_only_revoke_and_privacy(self):
        item=self.library();name,other=self.other();url=f"/api/library/questions/{item['_id']}"
        assert other('GET',url).status_code==404
        r=self.call('PUT',url+'/sharing',{'revision':1,'usernames':[name]});assert r.status_code==200
        shared=other('GET',url).json
        assert not {'working_copy','bank_id','shared_with'} & shared.keys()
        assert other('PATCH',url,{'revision':2,'create_version':True}).status_code==404
        s=other('POST','/api/surveys',{'title':'不公开的问卷名称'}).json
        imported=other('POST',f"/api/surveys/{s['_id']}/library-import",{'library_id':item['_id'],'version':item['current_version'],'question_id':'q1','revision':1})
        assert imported.status_code==200,imported.json
        usage=self.call('GET',url+'/usage').json
        assert usage['external_occurrences']==1 and usage['items']==[] and '不公开的问卷名称' not in str(usage)
        assert self.call('GET',url+'/statistics').json['groups']==[]
        assert other('GET',url+'/usage').status_code==404
        assert self.call('PUT',url+'/sharing',{'revision':r.json['revision'],'usernames':[]}).status_code==200
        assert other('GET',url).status_code==404
        assert other('GET',f"/api/surveys/{s['_id']}").json['questions']==imported.json['questions']
        assert self.call('GET',url).status_code==200

    def test_local_edit_keeps_provenance_and_separates_statistics(self):
        item=self.library();s1=self.import_to(item);s2=self.import_to(item,'other')
        edited=deepcopy(s2['questions'][0]);source=edited.pop('source');edited['options'][0]['label']='不同含义'
        r=self.call('PUT',f"/api/surveys/{s2['_id']}/questions/other",{'revision':s2['revision'],'question':edited})
        assert r.status_code==200,r.json
        s2=r.json;assert s2['questions'][0]['source']==source
        self.submit(s1,{'q1':'a'});self.submit(s2,{'other':'b'})
        groups=self.call('GET',f"/api/library/questions/{item['_id']}/statistics").json['groups']
        assert len(groups)==2 and sorted(g['answer_count'] for g in groups)==[1,1]
        assert sorted(g['locally_changed'] for g in groups)==[False,True]
        usage=self.call('GET',f"/api/library/questions/{item['_id']}/usage").json
        assert len(usage['items'])==2 and sum(u['locally_changed'] for u in usage['items'])==1

    def test_cross_survey_same_version_aggregation_and_zero(self):
        item=self.library('number');s1=self.import_to(item);s2=self.import_to(item,'age')
        self.submit(s1,{'q1':0});self.submit(s2,{'age':8})
        result=self.call('GET',f"/api/library/questions/{item['_id']}/statistics").json
        assert result['scope']=='owned_surveys_only'
        assert len(result['groups'])==1 and result['groups'][0]['answer_count']==2
        assert result['groups'][0]['average']==4
        oldstats=self.call('GET',f"/api/surveys/{s1['_id']}/statistics")
        assert oldstats.status_code==200

    def test_distinct_versions_not_silently_merged(self):
        item=self.library();old=item['current_version'];self.submit(self.import_to(item),{'q1':'a'})
        q=deepcopy(item['working_copy']);q['options'][0]['label']='非常满意'
        item=self.update(item,question=q,create_version=True)
        self.submit(self.import_to(item),{'q1':'b'})
        path=f"/api/library/questions/{item['_id']}/statistics"
        assert len(self.call('GET',path).json['groups'])==2
        selected=self.call('GET',path+'?version='+old).json['groups']
        assert len(selected)==1 and selected[0]['version']==old

    def test_conflicting_writes_reject_stale_revision(self):
        item=self.library();url=f"/api/library/questions/{item['_id']}"
        def write(title):
            q=deepcopy(item['working_copy']);q['title']=title
            with self.app.test_client() as client:
                return client.patch(url,json={'revision':1,'question':q,'create_version':True},headers=self.headers).status_code
        with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(write,['甲','乙']))
        assert sorted(statuses)==[200,409]
        assert len(self.call('GET',url).json['versions'])==2

    def test_bank_move_source_jump_removal_and_invalid_ids(self):
        bank=self.call('POST','/api/banks',{'title':'第一题库'}).json
        s=self.survey();q={'id':'q1','title':'是否继续','type':'single','options':[{'id':'a','label':'是'},{'id':'b','label':'否'}],
            'jumps':[{'op':'eq','value':'b','target':'END'}]}
        r=self.call('POST',f"/api/surveys/{s['_id']}/questions",{'question':q,'revision':1})
        assert r.status_code==200,r.json
        r=self.call('POST','/api/library/questions',{'bank_id':bank['_id'],'survey_id':s['_id'],'question_id':'q1'})
        assert r.status_code==201,r.json
        assert r.json['jumps_removed'] and r.json['item']['working_copy']['jumps']==[]
        item=r.json['item'];bank2=self.call('POST','/api/banks',{'title':'第二题库'}).json
        item=self.update(item,bank_id=bank2['_id'])
        assert self.call('GET','/api/library/questions?bank_id='+bank['_id']).json['total']==0
        assert self.call('GET','/api/library/questions?bank_id='+bank2['_id']).json['total']==1
        assert self.call('POST','/api/library/questions',{'bank_id':{'$ne':None},'question':{}}).status_code==400
        assert self.call('POST',f"/api/surveys/{s['_id']}/library-import",{'library_id':{'$ne':None}}).status_code==400

    def test_multiple_choice_counts_use_answer_occurrences(self):
        item=self.library('multiple');s=self.import_to(item)
        self.submit(s,{'q1':['a','b']})
        g=self.call('GET',f"/api/library/questions/{item['_id']}/statistics").json['groups'][0]
        assert g['answer_count']==1 and [o['count'] for o in g['options']]==[1,1]
