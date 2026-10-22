"""Editable, deterministic SVG schematics based on this project's actual code."""
from pathlib import Path
from html import escape

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/images'
INK='#253B3D';GRAY='#6D8386'
BLUE=('#EBF6F3','#8CB9AE');GOLD=('#F1F4F8','#A9B8CC')
PURPLE=('#FBEFE8','#D4AA96');GREEN=('#F2EFF8','#B6A6CC')


class SVG:
    def __init__(self,w,h,title):
        self.w,self.h=w,h
        self.items=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title"><title id="title">{escape(title)}</title>',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#728495"/></marker></defs>',
            '<rect width="100%" height="100%" fill="white"/>',
            '<g font-family="Microsoft YaHei,SimHei,sans-serif" fill="#24364B">']
    def rect(self,x,y,w,h,fill='white',stroke='#A7C5E1',radius=10):
        self.items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    def text(self,x,y,s,size=18,weight=400,anchor='middle',fill=INK):
        self.items.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(s)}</text>')
    def card(self,x,y,w,h,lines,color=BLUE,size=18):
        self.rect(x,y,w,h,*color)
        start=y+h/2-(len(lines)-1)*13+6
        for i,s in enumerate(lines):self.text(x+w/2,start+i*26,s,size,600 if i==0 else 400)
    def path(self,d,dashed=False):
        dash=' stroke-dasharray="5 5"' if dashed else ''
        self.items.append(f'<path d="{d}" fill="none" stroke="{GRAY}" stroke-width="1.7"{dash} marker-end="url(#arrow)"/>')
    def label(self,x,y,text):
        w=len(text)*13+18;self.rect(x-w/2,y-15,w,23,'white','none',0);self.text(x,y+2,text,14)
    def cylinder(self,x,y,w,h,title,sub):
        self.items.append(f'<path d="M{x} {y+15}V{y+h-15}C{x} {y+h+5} {x+w} {y+h+5} {x+w} {y+h-15}V{y+15}" fill="white" stroke="{GREEN[1]}" stroke-width="1.5"/>')
        self.items.append(f'<ellipse cx="{x+w/2}" cy="{y+15}" rx="{w/2}" ry="15" fill="white" stroke="{GREEN[1]}" stroke-width="1.5"/>')
        self.text(x+w/2,y+49,title,18,600);self.text(x+w/2,y+77,sub,16)
    def save(self,path):
        path.write_text(''.join(self.items)+'</g></svg>',encoding='utf-8')


def architecture():
    s=SVG(1200,985,'问卷系统分层架构：浏览器、Flask后端、规则模块与MongoDB五集合')
    s.card(450,18,300,68,['使用者','问卷创建者 / 登录填写者'],('#285E60','#285E60'))
    # Dark actor card has white labels.
    s.items[-2:]=[x.replace(f'fill="{INK}"','fill="white"') for x in s.items[-2:]]
    s.path('M600 86V119')
    s.rect(30,120,1140,142,*BLUE);s.text(600,149,'01  页面交互 · HTML / CSS / JavaScript',20,600)
    front=[(60,'账号与工作台','登录 / 本人问卷'),(340,'问卷编辑','题目 / 校验 / 规则'),(620,'分享填写','逐题填写 / 恢复进度'),(900,'统计与答卷','整卷 / 单题 / 分页')]
    for x,a,b in front:s.card(x,170,240,70,[a,b],('white',BLUE[1]),17)
    s.path('M600 262V319');s.label(600,291,'HTTP / JSON · Bearer Token')
    s.rect(30,320,1140,420,*GOLD);s.text(600,350,'02  服务与规则 · Python Flask',20,600)
    s.card(385,373,430,72,['API 入口与访问控制','JSON结构 · 登录会话 · 问卷归属 · 状态检查'],('#DAE5ED',GOLD[1]),18)
    for x,a,b in [(65,'问卷管理','草稿编辑 / 发布冻结'),(345,'账号与会话','密码哈希 / 令牌摘要'),(625,'进度与提交','有效路径 / 防重与重试'),(905,'统计与查询','聚合计数 / 匿名脱敏')]:
        s.path(f'M600 445V465H{x+115}V490');s.card(x,490,230,72,[a,b],('white',GOLD[1]),17)
    s.rect(65,602,350,105,*PURPLE);s.text(240,632,'规则与校验模块',19,600);s.text(240,662,'validation.py · logic.py',18);s.text(240,689,'定义校验 / 回答校验 / 路径计算',16)
    s.card(555,623,425,74,['数据访问 · PyMongo','CRUD · 条件更新 · 唯一索引 · 聚合'],('#DAE5ED',GOLD[1]),18)
    s.path('M180 562V580H210V600',True);s.path('M740 562V581H355V600',True)
    s.path('M460 562V610H665V620');s.path('M740 562V620');s.path('M1020 562V660H982')
    s.path('M415 658H552',True);s.label(486,638,'校验后写入')
    s.path('M765 697V781');s.label(887,762,'数据库操作')
    s.rect(30,782,1140,155,*GREEN);s.text(600,811,'03  文档存储 · MongoDB（业务数据持久化）',20,600)
    for x,t,sub in [(55,'users','用户账号'),(280,'sessions','登录会话'),(505,'surveys','问卷与嵌入题目'),(730,'fill_progress','已确认进度'),(955,'responses','正式答卷')]:s.cylinder(x,828,190,94,t,sub)
    s.text(600,971,'实线：请求或数据访问；虚线：模块调用。未提交进度不参与统计；当前未使用跨集合事务。',16)
    s.save(OUT/'stage1-architecture-final.svg')


def model():
    s=SVG(1200,770,'五集合关系：用户引用、问卷内嵌题目、进度与答卷独立保存')
    s.rect(25,25,1150,165,*BLUE);s.text(58,57,'账号与访问',20,600,'start')
    s.card(65,83,280,78,['users','账号 / 密码哈希 / 创建时间'],('white',BLUE[1]),18)
    s.card(620,83,485,78,['sessions · 登录会话','user_id / expires_at / 令牌摘要'],('white',BLUE[1]),18)
    s.path('M620 122H348');s.label(482,105,'user_id 引用用户')
    s.rect(25,234,1150,253,*GOLD);s.text(58,267,'问卷定义 · 数量有限的配置嵌入保存',20,600,'start')
    s.card(65,295,300,151,['surveys','owner_id / title / status','revision / deadline'],('white',GOLD[1]),19)
    s.path('M205 190V232');s.label(349,215,'owner_id · 一位创建者可有多份问卷')
    s.rect(445,291,660,163,'#FAFBFD',GOLD[1]);s.text(775,322,'questions[] · 嵌入问卷',21,600)
    for x,t,u in [(469,'题目与选项','id / type / options[]'),(681,'回答校验','validation{}'),(893,'条件跳转','jumps[]')]:s.card(x,342,188,82,[t,u],('white',GOLD[1]),16)
    s.path('M365 370H442');s.label(405,350,'嵌入')
    s.rect(25,543,1150,168,*GREEN);s.text(58,576,'填写与提交 · 独立文档，避免问卷持续膨胀',20,600,'start')
    s.card(65,595,475,87,['fill_progress · 活动进度','answers{} / revision / request_id','每账号每问卷一份；不计入统计'],('white',GREEN[1]),18)
    s.card(630,595,475,87,['responses · 正式答卷','answers[] / path[] / request_id','每次成功提交一份；作为统计来源'],('white',GREEN[1]),18)
    s.path('M220 487V592');s.path('M974 487V592');s.label(350,516,'survey_id / user_id 引用');s.label(935,516,'survey_id / user_id 引用')
    s.text(600,748,'数组与对象框表示嵌入结构；集合通过字符串 ID 关联，由后端校验，不是数据库外键。',17)
    s.save(OUT/'stage1-data-model-final.svg')


if __name__=='__main__':
    architecture();model();print('Two SVG diagrams generated from reviewed implementation.')
