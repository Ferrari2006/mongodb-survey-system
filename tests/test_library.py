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
        assert self.client.get('/api/health').json['milestone']=='stage2'
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

    def test_numeric_distribution_and_optional_skipped_answers(self):
        item=self.library('number');q=deepcopy(item['working_copy']);q['required']=False
        item=self.update(item,question=q,create_version=True)
        empty=self.import_to(item);zero=self.import_to(item);eight=self.import_to(item)
        self.submit(empty,{'q1':None});self.submit(zero,{'q1':0});self.submit(eight,{'q1':8})
        g=self.call('GET',f"/api/library/questions/{item['_id']}/statistics").json['groups'][0]
        assert g['answer_count']==2 and g['average']==4 and g['minimum']==0 and g['maximum']==8
        assert sum(b['count'] for b in g['distribution'])==2
        assert g['distribution'][0]['minimum']==0 and g['distribution'][-1]['upper_inclusive']
        assert all(not b['upper_inclusive'] for b in g['distribution'][:-1])

    def test_empty_numeric_distribution(self):
        item=self.library('number');self.import_to(item)
        g=self.call('GET',f"/api/library/questions/{item['_id']}/statistics").json['groups'][0]
        assert g['answer_count']==0 and g['average'] is None and g['distribution']==[]

    def test_text_answers_are_paged_and_ordered(self):
        item=self.library('text');s=self.import_to(item)
        sid=s['_id'];r=self.call('PATCH',f'/api/surveys/{sid}',{'revision':s['revision'],'allow_repeat':True})
        self.submit(r.json,{'q1':'回答00'})
        for i in range(1,23):
            r=self.call('POST',f'/api/public/surveys/{sid}/responses',{'answers':{'q1':f'回答{i:02}'},'request_id':uuid4().hex})
            assert r.status_code==201,r.json
        path=f"/api/library/questions/{item['_id']}/statistics"
        first=self.call('GET',path).json['groups'][0];second=self.call('GET',path+'?page=2').json['groups'][0]
        assert first['answer_count']==23 and len(first['values'])==20
        assert second['values']==['回答20','回答21','回答22'] and second['page']==2
        assert first['values'][0]=='回答00'
        assert self.call('GET',path+'?page=0').status_code==400

    def test_shared_user_sees_only_own_cross_survey_answers(self):
        item=self.library();self.submit(self.import_to(item),{'q1':'a'})
        name,other=self.other();url=f"/api/library/questions/{item['_id']}"
        shared=self.call('PUT',url+'/sharing',{'revision':item['revision'],'usernames':[name]})
        assert shared.status_code==200
        s=other('POST','/api/surveys',{'title':'另一账号答卷隔离'}).json
        r=other('POST',f"/api/surveys/{s['_id']}/library-import",{'library_id':item['_id'],'version':item['current_version'],'question_id':'other','revision':1})
        assert r.status_code==200
        r=other('POST',f"/api/surveys/{s['_id']}/publish",{'revision':r.json['revision']})
        assert r.status_code==200
        assert other('POST',f"/api/public/surveys/{s['_id']}/responses",{'answers':{'other':'b'},'request_id':uuid4().hex}).status_code==201
        owner=self.call('GET',url+'/statistics').json['groups'][0]
        receiver=other('GET',url+'/statistics').json['groups'][0]
        assert owner['answer_count']==receiver['answer_count']==1
        assert [o['count'] for o in owner['options']]==[1,0]
        assert [o['count'] for o in receiver['options']]==[0,1]

    def test_invalid_import_and_unknown_sharing_leave_data_unchanged(self):
        item=self.library();s=self.import_to(item);path=f"/api/surveys/{s['_id']}/library-import"
        original=deepcopy(s['questions'])
        base={'revision':s['revision'],'question_id':'q1','library_id':item['_id'],'version':item['current_version']}
        assert self.call('POST',path,base).status_code==400
        assert self.call('POST',path,{**base,'question_id':'q2','version':'missing'}).status_code==404
        assert self.call('POST',path,{**base,'question_id':'q2','revision':1}).status_code==409
        assert self.call('GET',f"/api/surveys/{s['_id']}").json['questions']==original
        url=f"/api/library/questions/{item['_id']}"
        r=self.call('PUT',url+'/sharing',{'revision':item['revision'],'usernames':['nobody_'+uuid4().hex[:10]]})
        assert r.status_code==400
        assert self.call('GET',url).json['revision']==item['revision']
