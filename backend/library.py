"""Stage-two question banks: immutable versions and copied survey definitions."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from flask import g, jsonify, request
from backend.validation import DomainError, identifier, question, require, string


def definition_hash(item):
    """Conservatively separate any local definition change; jumps are survey-local."""
    return hashlib.sha256(json.dumps({k:v for k,v in item.items() if k not in
        ('id', 'jumps', 'source')}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def template(item):
    require(isinstance(item, dict), '题目须为对象')
    item = deepcopy(item)
    item['id'] = 'template'
    require(not item.get('jumps'), '题库题不保存问卷跳转，请先移除跳转后保存')
    result = question(item)
    return result


def register_library(app, db, login_required, payload, owned, save):
    def now(): return datetime.now(timezone.utc)

    def pagination():
        try: page = int(request.args.get('page', '1'))
        except ValueError: raise DomainError('page须为正整数') from None
        require(1 <= page <= 10000, 'page须在1～10000之间')
        return page

    def bank_owned(bid):
        require(isinstance(bid, str), 'bank_id须为文本ID')
        bank = db.question_banks.find_one({'_id':bid, 'owner_id':g.user_id})
        if not bank: raise DomainError('题库不存在或无权访问', 404, 'not_found')
        return bank

    def accessible(lid, owner=False):
        require(isinstance(lid, str), 'library_id须为文本ID')
        query = {'_id':lid}
        if owner: query['owner_id'] = g.user_id
        else: query['$or'] = [{'owner_id':g.user_id}, {'shared_with':g.user_id}]
        item = db.library_questions.find_one(query)
        if not item: raise DomainError('题目不存在或无权访问', 404, 'not_found')
        return item

    def clean(item):
        result = deepcopy(item)
        result['is_owner'] = result['owner_id'] == g.user_id
        if not result['is_owner']:
            for key in ('working_copy','shared_with','bank_id'): result.pop(key,None)
        else:
            result['shared_usernames'] = [u['username'] for u in db.users.find(
                {'_id':{'$in':result.get('shared_with',[])}}, {'username':1}).sort('username',1)]
        return result

    def cas(item, data, updates):
        revision = data.get('revision')
        require(type(revision) is int and revision >= 1, '须提供整数revision')
        if revision != item['revision']:
            raise DomainError('题目已修改，请刷新后重试',409,'library_conflict')
        updates.update(updated_at=now())
        result = db.library_questions.update_one({'_id':item['_id'], 'owner_id':g.user_id,
            'revision':item['revision']}, {'$set':updates, '$inc':{'revision':1}})
        if not result.matched_count:
            raise DomainError('题目已修改，请刷新后重试',409,'library_conflict')
        return jsonify(clean(accessible(item['_id'],True)))

    def version(item, vid):
        require(isinstance(vid,str), 'version须为版本ID')
        result = next((v for v in item['versions'] if v['id'] == vid),None)
        if not result: raise DomainError('指定版本不存在',404,'version_not_found')
        return result

    @app.get('/api/banks')
    @login_required
    def list_banks():
        page=pagination();q={'owner_id':g.user_id}
        return jsonify(items=list(db.question_banks.find(q).sort('created_at',-1).skip((page-1)*20).limit(20)),
                       total=db.question_banks.count_documents(q),page=page)

    @app.post('/api/banks')
    @login_required
    def create_bank():
        data=payload({'title','description'})
        bank={'_id':uuid4().hex,'owner_id':g.user_id,'title':string(data.get('title'),'题库名称',1,100),
              'description':string(data.get('description',''),'题库说明',0,1000),'created_at':now()}
        db.question_banks.insert_one(bank)
        return jsonify(bank),201

    @app.patch('/api/banks/<bid>')
    @login_required
    def rename_bank(bid):
        bank_owned(bid);data=payload({'title','description'})
        updates={}
        for key,maxlen in [('title',100),('description',1000)]:
            if key in data: updates[key]=string(data[key],key,1 if key=='title' else 0,maxlen)
        require(bool(updates),'没有修改内容')
        db.question_banks.update_one({'_id':bid,'owner_id':g.user_id},{'$set':updates})
        return jsonify(bank_owned(bid))

    @app.get('/api/library/questions')
    @login_required
    def list_library():
        page=pagination();scope=request.args.get('scope','mine')
        require(scope in ('mine','shared'),'scope须为mine或shared')
        q={'owner_id':g.user_id} if scope=='mine' else {'shared_with':g.user_id,'owner_id':{'$ne':g.user_id}}
        if request.args.get('bank_id'):
            require(scope=='mine','共享题不按他人题库分组查询');bank_owned(request.args['bank_id']);q['bank_id']=request.args['bank_id']
        items=list(db.library_questions.find(q,{'versions':0,'working_copy':0,'shared_with':0}).sort('updated_at',-1).skip((page-1)*20).limit(20))
        for item in items:
            item['is_owner']=item['owner_id']==g.user_id
            if not item['is_owner']: item.pop('bank_id',None)
        return jsonify(items=items,total=db.library_questions.count_documents(q),page=page)

    @app.post('/api/library/questions')
    @login_required
    def create_library_question():
        data=payload({'bank_id','question','survey_id','question_id'})
        bank=bank_owned(data.get('bank_id'));removed=False
        if 'survey_id' in data:
            require('question' not in data,'不能同时指定问卷来源和题目定义')
            require(isinstance(data['survey_id'], str), 'survey_id须为文本ID')
            survey=owned(data['survey_id'])
            original=next((q for q in survey['questions'] if q['id']==data.get('question_id')),None)
            require(original is not None,'问卷题目不存在')
            content={k:deepcopy(v) for k,v in original.items() if k in {'id','title','type','required','options','validation','jumps'}}
            removed=bool(content.get('jumps'));content['jumps']=[]
        else: content=data.get('question')
        content=template(content);vid=uuid4().hex;stamp=now()
        v={'id':vid,'number':1,'parent_version':None,'restored_from':None,'question':content,'created_at':stamp}
        item={'_id':uuid4().hex,'owner_id':g.user_id,'bank_id':bank['_id'],'title':content['title'],
              'working_copy':content,'versions':[v],'current_version':vid,'revision':1,'shared_with':[],
              'created_at':stamp,'updated_at':stamp}
        db.library_questions.insert_one(item)
        return jsonify(item=clean(item),jumps_removed=removed),201

    @app.get('/api/library/questions/<lid>')
    @login_required
    def get_library_question(lid):
        return jsonify(clean(accessible(lid)))

    @app.patch('/api/library/questions/<lid>')
    @login_required
    def update_library_question(lid):
        item=accessible(lid,True);data=payload({'revision','question','create_version','base_version','bank_id'})
        create=data.get('create_version',False);require(type(create) is bool,'create_version须为布尔值')
        content=template(data['question']) if 'question' in data else item['working_copy']
        updates={'working_copy':content}
        if 'bank_id' in data:updates['bank_id']=bank_owned(data['bank_id'])['_id']
        if create:
            require(len(item['versions'])<100,'每题最多100个已提交版本')
            parent=version(item,data.get('base_version',item['current_version']))
            vid=uuid4().hex
            versions=item['versions']+[{'id':vid,'number':len(item['versions'])+1,'parent_version':parent['id'],
                'restored_from':None,'question':content,'created_at':now()}]
            updates.update(versions=versions,current_version=vid,title=content['title'])
        return cas(item,data,updates)

    @app.post('/api/library/questions/<lid>/restore')
    @login_required
    def restore_library_question(lid):
        item=accessible(lid,True);data=payload({'revision','version'});old=version(item,data.get('version'))
        require(len(item['versions'])<100,'每题最多100个已提交版本');vid=uuid4().hex
        restored={'id':vid,'number':len(item['versions'])+1,'parent_version':item['current_version'],
                  'restored_from':old['id'],'question':deepcopy(old['question']),'created_at':now()}
        return cas(item,data,{'versions':item['versions']+[restored],'current_version':vid,
                             'working_copy':restored['question'],'title':restored['question']['title']})

    @app.put('/api/library/questions/<lid>/sharing')
    @login_required
    def share_library_question(lid):
        item=accessible(lid,True);data=payload({'revision','usernames'});names=data.get('usernames')
        require(isinstance(names,list) and len(names)<=100 and all(isinstance(n,str) for n in names),'usernames须为至多100个用户名')
        names=set(string(n,'用户名',3,32).lower() for n in names)
        users=list(db.users.find({'username':{'$in':sorted(names)}},{'_id':1,'username':1}))
        require({u['username'] for u in users}==names,'分享对象中有不存在的账号')
        return cas(item,data,{'shared_with':sorted(u['_id'] for u in users if u['_id']!=g.user_id)})

    @app.post('/api/surveys/<sid>/library-import')
    @login_required
    def import_library_question(sid):
        data=payload({'library_id','version','question_id','revision'})
        survey=owned(sid);item=accessible(data.get('library_id'));v=version(item,data.get('version'))
        q=deepcopy(v['question']);q['id']=identifier(data.get('question_id'),'本卷题目ID')
        require(q['id']!='END','END为结束标识');require(len(survey['questions'])<100,'每份问卷最多100题')
        require(q['id'] not in {q['id'] for q in survey['questions']},'本卷题目ID重复')
        q['source']={'library_id':item['_id'],'version':v['id'],'definition_hash':definition_hash(q)}
        survey['questions'].append(q)
        return save(survey,data.get('revision'))

    @app.get('/api/library/questions/<lid>/usage')
    @login_required
    def library_usage(lid):
        accessible(lid,True)
        pipeline=[{'$match':{'questions.source.library_id':lid}},{'$unwind':'$questions'},
                  {'$match':{'questions.source.library_id':lid}},
                  {'$group':{'_id':'$owner_id','count':{'$sum':1}}}]
        counts=list(db.surveys.aggregate(pipeline))
        own=list(db.surveys.find({'owner_id':g.user_id,'questions.source.library_id':lid}))
        items=[{'survey_id':s['_id'],'title':s['title'],'status':s['status'],'question_id':q['id'],
                'version':q['source']['version'],'locally_changed':definition_hash(q)!=q['source']['definition_hash']}
               for s in own for q in s['questions'] if q.get('source',{}).get('library_id')==lid]
        return jsonify(items=items,external_occurrences=sum(r['count'] for r in counts if r['_id']!=g.user_id),
                       counting_unit='question_occurrence')

    @app.get('/api/library/questions/<lid>/statistics')
    @login_required
    def cross_survey_statistics(lid):
        item=accessible(lid)
        text_page=pagination()
        text_offset=(text_page-1)*20
        selected=request.args.get('version')
        if selected:version(item,selected)
        surveys=list(db.surveys.find({'owner_id':g.user_id,'questions.source.library_id':lid}))
        groups={}
        branches=[];match=[]
        for survey in surveys:
            for q in survey['questions']:
                source=q.get('source',{})
                if source.get('library_id')!=lid or selected and source['version']!=selected:continue
                key=source['version']+':'+definition_hash(q)
                groups.setdefault(key,{'key':key,'version':source['version'],'definition_hash':definition_hash(q),
                    'title':q['title'],'type':q['type'],'question':q,'instances':[],
                    'locally_changed':definition_hash(q)!=source['definition_hash']})
                groups[key]['instances'].append({'survey_id':survey['_id'],'question_id':q['id']})
                condition={'survey_id':survey['_id'],'answers.question_id':q['id']};match.append(condition)
                branches.append({'case':{'$and':[{'$eq':['$survey_id',survey['_id']]},{'$eq':['$answers.question_id',q['id']]}]},'then':key})
        # Each answer occurrence belongs to exactly one local question and compatibility group.
        facets={
            'counts':[{'$group':{'_id':'$_group','count':{'$sum':1}}}],
            'options':[{'$match':{'_group':{'$in':[k for k,v in groups.items() if v['type'] in ('single','multiple')]}}},
                {'$unwind':'$answers.value'},{'$group':{'_id':{'g':'$_group','value':'$answers.value'},'count':{'$sum':1}}}],
            'numbers':[{'$match':{'answers.value':{'$type':'number'}}},{'$group':{'_id':'$_group',
                'average':{'$avg':'$answers.value'},'minimum':{'$min':'$answers.value'},'maximum':{'$max':'$answers.value'}}}]
        }
        # Page text and bucket numbers inside their facets, so the returned document
        # does not grow with every text answer. All groups use the same answer input.
        for i,(key,group) in enumerate(groups.items()):
            if group['type']=='number':
                facets[f'distribution_{i}']=[{'$match':{'_group':key}},
                    {'$bucketAuto':{'groupBy':'$answers.value','buckets':10}}]
            elif group['type']=='text':
                facets[f'text_{i}']=[{'$match':{'_group':key}},
                    {'$sort':{'created_at':1,'_id':1}}, {'$skip':text_offset},{'$limit':20},
                    {'$project':{'_id':0,'value':'$answers.value'}}]
        data={key:[] for key in facets}
        if match:
            data=list(db.responses.aggregate([
                {'$match':{'survey_id':{'$in':[s['_id'] for s in surveys]}}},
                {'$unwind':'$answers'},{'$match':{'$or':match}},
                {'$set':{'_group':{'$switch':{'branches':branches,'default':None}}}},
                {'$facet':facets}]))[0]
        counts={r['_id']:r['count'] for r in data['counts']}
        options={(r['_id']['g'],r['_id']['value']):r['count'] for r in data['options']}
        numbers={r['_id']:r for r in data['numbers']}
        for i,(key,group) in enumerate(groups.items()):
            q=group.pop('question');group['answer_count']=counts.get(key,0)
            if q['type'] in ('single','multiple'):group['options']=[{**o,'count':options.get((key,o['id']),0)} for o in q['options']]
            elif q['type']=='number':
                summary=numbers.get(key,{})
                for field in ('average','minimum','maximum'):group[field]=summary.get(field)
                group['distribution']=[{'minimum':b['_id']['min'],'maximum':b['_id']['max'],
                    'count':b['count'],'upper_inclusive':j==len(data[f'distribution_{i}'])-1}
                    for j,b in enumerate(data[f'distribution_{i}'])]
                group['distribution_method']='automatic_buckets_up_to_10'
            else:
                group['values']=[r['value'] for r in data[f'text_{i}']]
                group['page']=text_page;group['page_size']=20
        return jsonify(library_id=lid,scope='owned_surveys_only',counting_unit='answered_question_occurrence',groups=list(groups.values()))
