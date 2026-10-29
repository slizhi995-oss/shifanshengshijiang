"""Create a representative Word sample using the bundled artifact Python."""
import ast
import importlib.util
import sys
import types
import json
import sqlite3
import re
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tmp/word-qa-deps'))
sys.path.insert(0,str(root/'backend'))
package=types.ModuleType('lesson_qa');package.__path__=[];sys.modules['lesson_qa']=package
content_spec=importlib.util.spec_from_file_location('lesson_qa.lesson_content',root/'backend/app/services/lesson_content.py')
content_module=importlib.util.module_from_spec(content_spec);sys.modules[content_spec.name]=content_module;content_spec.loader.exec_module(content_module)
spec=importlib.util.spec_from_file_location('lesson_qa.lesson_word',root/'backend/app/services/lesson_word.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
build_lesson_docx=module.build_lesson_docx

tree=ast.parse((root/'backend/tests/test_lesson_word.py').read_text(encoding='utf-8'))
source=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SOURCE' for t in node.targets))
identifier='tb-'+str(2).zfill(32)
source+='\n\n![伽利略斜面实验频闪照片](/api/v1/textbooks/assets/'+identifier+'/image)\n\n教材来源：高中物理必修第一册 第四章 PDF第88页。'
image=root/'必修第一册图片/02_图4.1-1_伽利略斜面实验.png'
output=root/'backend/outputs/lesson-word'
output.mkdir(parents=True,exist_ok=True)
(output/'fixture.docx').write_bytes(build_lesson_docx(source,'牛顿第一定律',{identifier:image}))
(output/'source.txt').write_text(source,encoding='utf-8')
print(output/'fixture.docx')

# A real saved lesson catches multi-page layouts, nested lists, preparation
# tables and illustrations that a short synthetic example cannot exercise.
with sqlite3.connect((root/'backend/app.db').as_uri()+'?mode=ro',uri=True) as db:
    lesson=db.execute('SELECT id,title,content FROM textbook_lessons ORDER BY id DESC LIMIT 1').fetchone()
    if lesson:
        images={}
        for identifier in set(re.findall(r'tb-[a-f0-9]{32}',lesson[2])):
            row=db.execute('SELECT file_path FROM textbook_assets WHERE asset_id=?',(identifier,)).fetchone()
            if row:
                path=(root/'backend/private_textbooks'/row[0]).resolve()
                if path.is_file() and path.is_relative_to((root/'backend/private_textbooks').resolve()):images[identifier]=path
        (output/'real-lesson.docx').write_bytes(build_lesson_docx(lesson[2],lesson[1],images))
        (output/'real-lesson-source.txt').write_text(lesson[2],encoding='utf-8')
        (output/'qa-source.json').write_text(json.dumps({'lesson_id':lesson[0],'title':lesson[1]},ensure_ascii=False),encoding='utf-8')
        print(output/'real-lesson.docx')
