"""Draw the stage-two relationships using the established course report palette."""
from pathlib import Path
from draw_layered_architecture import SVG as BaseSVG


class SVG(BaseSVG):
    def __init__(self, *args):
        super().__init__(*args)
        self.items=[s.replace('Microsoft YaHei,SimHei,sans-serif', 'Arial,Microsoft YaHei,sans-serif') for s in self.items]
        self.items.append('<defs><marker id="restore-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#8F80A6"/></marker></defs>')

    def text(self, x, y, s, size=18, weight=400, anchor='middle', fill='#253B3D'):
        super().text(x,y,s,size,weight,anchor,fill)

    def path(self,d,dashed=False):
        if not dashed:return super().path(d)
        self.items.append(f'<path d="{d}" fill="none" stroke="#8F80A6" stroke-width="2" stroke-dasharray="7 6" marker-end="url(#restore-arrow)"/>')

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '第二阶段/images'
TEAL = ('#EBF6F3', '#8CB9AE')
SLATE = ('#F1F4F8', '#A9B8CC')
PEACH = ('#FBEFE8', '#D4AA96')
LAVENDER = ('#F2EFF8', '#B6A6CC')


def box(s, x, y, w, h, title, lines, color):
    s.rect(x, y, w, h, *color, radius=12)
    s.text(x + 24, y + 37, title, 25, 600, 'start')
    for i, line in enumerate(lines):
        s.text(x + 24, y + 76 + i * 31, line, 21, anchor='start')


def section_title(s,x,y,number,title,color):
    s.rect(x,y-27,42,36,color,'none',8)
    s.text(x+21,y-1,number,22,600,fill='white')
    s.text(x+56,y,title,26,600,'start')


def note(s, x, y, text, width):
    s.rect(x - width / 2, y - 24, width, 33, 'white', 'none', 4)
    s.text(x, y, text, 21)


def data_flow():
    s = SVG(1200, 530, '题库来源、问卷副本与正式答卷的关系；跨卷统计只读取本人问卷')
    for x, number, title, color, accent in [(20, '01', '可复用来源', TEAL,'#487C73'),
                             (420, '02', '问卷内容', SLATE,'#586F8B'),
                             (820, '03', '正式答卷', PEACH,'#A56C55')]:
        s.rect(x, 20, 360, 335, *color, radius=14)
        section_title(s,x+22,60,number,title,accent)
    box(s, 40, 85, 320, 95, 'question_banks', ['按所有者管理与分组'], ('white', TEAL[1]))
    box(s, 40, 200, 320, 134, 'library_questions',
        ['工作稿 · 已提交版本', '共享名单 · 当前版本指针'], ('white', TEAL[1]))
    box(s, 440, 85, 320, 249, 'surveys.questions',
        ['复制选定版本的题目定义', 'source 记录来源与版本', '定义摘要用于区分改题', '发布后保持问卷内容不变'], ('white', SLATE[1]))
    box(s, 840, 85, 320, 249, 'responses',
        ['独立保存正式答卷', '关联问卷及本卷题号', '记录实际填写路径', '未提交进度不参与统计'], ('white', PEACH[1]))
    s.path('M360 267H440')
    note(s, 400, 250, '导入', 58)
    s.path('M760 267H840')
    note(s, 800, 250, '提交', 58)
    # Statistical input is the owner's surveys and their submitted responses.
    s.path('M600 355V388')
    s.path('M1000 355V388')
    note(s, 700, 379, '来源题定位', 180)
    note(s, 1090, 379, '有效作答', 160)
    box(s, 420, 390, 760, 120, '跨问卷统计 · 限本人管理的问卷',
        ['按来源版本与实际定义分组，再汇总本人问卷中的有效作答'], LAVENDER)
    box(s, 20, 390, 360, 120, '保持旧问卷独立',
        ['题库改版不反向覆盖副本'], TEAL)
    s.save(OUT / 'stage2-data-flow-refined.svg')


def version_flow():
    s = SVG(1200, 500, '题目版本分支与恢复：父版本关系和恢复内容来源分别记录')
    s.rect(20, 20, 1160, 200, *SLATE, radius=14)
    section_title(s,44,59,'01','历史版本 · 已提交内容保留','#586F8B')
    box(s, 40, 80, 290, 130, '版本 1', ['首次提交的题目内容', '作为分支与恢复来源'], ('white', SLATE[1]))
    box(s, 455, 80, 290, 130, '版本 2', ['在版本 1 上修改', 'parent_version → 1'], ('white', SLATE[1]))
    box(s, 870, 80, 290, 130, '版本 3', ['在版本 2 上修改', 'parent_version → 2'], ('white', SLATE[1]))
    s.path('M330 145H455'); s.path('M745 145H870')
    s.rect(420, 267, 760, 150, *TEAL, radius=14)
    box(s, 40, 280, 290, 124, '恢复保留历史',
        ['新增记录，不覆盖旧版本', '父版本与内容来源分别记录'], LAVENDER)
    box(s, 440, 280, 320, 124, '版本 4 · 历史分支',
        ['重新选择版本 1 作为起点', 'parent_version → 1'], ('white', TEAL[1]))
    box(s, 870, 280, 290, 124, '版本 5 · 恢复旧内容',
        ['parent_version → 4', 'restored_from → 1'], PEACH)
    s.path('M185 210V240H600V280')
    note(s, 600, 250, '从版本 1 创建分支', 260)
    s.path('M760 342H870')
    note(s, 1015, 250, '在当前版本 4 上执行恢复', 300)
    s.path('M40 145H12V446H1015V404', True)
    note(s, 610, 452, '虚线：恢复内容来自版本 1；原历史不被覆盖', 660)
    s.text(600, 490, '实线表示父版本关系；版本序号按提交次序递增，不代表只能顺序修改。', 21)
    s.save(OUT / 'stage2-version-flow-refined.svg')


if __name__ == '__main__':
    data_flow()
    version_flow()
    print('Two refined SVG figures saved; original figures retained.')
