"""Build FreshIN pages and video covers without modifying the original MP4 files."""
import base64
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
TOPICS = [
 ('fresh-air-function', 'Fresh Air Function'),
 ('air-quality-visualization', 'Air Quality Visualization'),
 ('gentle-breeze', 'Gentle Breeze'),
 ('smart-voice-control', 'Smart Voice Control'),
 ('voice-language-switching', 'Voice Language Switching'),
 ('app-connection', 'APP Connection'),
 ('smart-energy-saving', 'Smart Energy Saving'),
 ('electricity-consumption-visualization', 'Electricity Consumption Visualization'),
 ('arrive-leave-home-mode', 'Arrive / Leave Home Mode'),
 ('quadrupuri-filters', 'QuadruPuri Filters'),
 ('self-cleaning', 'Self-Cleaning'),
 ('gen-mode', 'GEN Mode'),
]

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def cover(video):
    for seek in ('0.15', '0'):
        result = subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',seek,'-i',str(video),'-map','0:v:0','-frames:v','1','-vf','scale=480:-2','-c:v','mjpeg','-q:v','8','-threads','1','-f','image2pipe','pipe:1'], capture_output=True, timeout=60)
        if result.returncode == 0 and result.stdout.startswith(b'\xff\xd8'): return result.stdout
    raise RuntimeError('Could not extract cover from ' + str(video))

def build(destination):
    destination = destination.resolve()
    same = destination == ROOT
    if not same and destination.exists() and any(destination.iterdir()):
        raise ValueError('Output directory must be empty, or use --in-place')
    destination.mkdir(parents=True, exist_ok=True)
    template = (ROOT/'template.html').read_text()
    player = (ROOT/'player.js').read_text()
    worker = (ROOT/'sw-template.js').read_text()
    logo = ROOT/'brand-logo.png'
    logo_version = digest(logo)[:16]
    if not same: shutil.copyfile(logo, destination/'brand-logo.png')
    topics = []
    for slug, title in TOPICS:
        video = ROOT/slug/(slug+'.mp4')
        item = {'slug':slug, 'title':title, 'file':None, 'cover':None}
        if video.is_file():
            media_hash = digest(video)
            image = cover(video)
            name = 'covers/'+slug+'.'+hashlib.sha256(image).hexdigest()[:16]+'.jpg'
            (destination/'covers').mkdir(exist_ok=True)
            (destination/name).write_bytes(image)
            item.update(file=slug+'/'+video.name+'?v='+media_hash[:16], hash=media_hash, bytes=video.stat().st_size, cover=name)
            if not same:
                (destination/slug).mkdir(exist_ok=True)
                shutil.copyfile(video, destination/slug/video.name)
        topics.append(item)
    version = hashlib.sha256((player+worker+template+Path(__file__).read_text()+logo_version+json.dumps(topics,sort_keys=True)).encode()).hexdigest()[:16]
    def attach(page, root):
        data=json.dumps({'version':version,'root':root,'topics':topics},ensure_ascii=False).replace('<',r'\u003c')
        scripts='<script id="videoCatalog" type="application/json">'+data+'</script>\n<script>\n'+player+'</script>\n'
        return page.replace('brand-logo.png"','brand-logo.png?v='+logo_version+'"').replace('</body>',scripts+'</body>')
    for item in topics:
        slug, title = item['slug'], html.escape(item['title'])
        links='\n'.join('            <a class="video-link" href="../'+s+'/"'+(' aria-current="page"' if s==slug else '')+'>'+html.escape(t)+'</a>' for s,t in TOPICS)
        page=template.replace('{{TITLE}}',title).replace('{{SLUG}}',slug).replace('{{LINKS}}',links)
        if item['file']:
            image=base64.b64encode((destination/item['cover']).read_bytes()).decode()
            page=page.replace('<!-- VIDEO_COVER -->','<img src="data:image/jpeg;base64,'+image+'" alt="">')
            page=page.replace(slug+'.mp4"',slug+'.mp4?v='+item['hash'][:16]+'"')
        else:
            page=re.sub(r'<div class="video-box">.*?(?=<nav class="video-directory")','<p role="status">Video coming soon.</p>\n    ',page,count=1,flags=re.S)
        (destination/slug).mkdir(exist_ok=True)
        (destination/slug/'index.html').write_text(attach(page,'../'))
    links='\n'.join('            <a class="video-link" href="./'+s+'/">'+html.escape(t)+'</a>' for s,t in TOPICS)
    home=template.replace('{{TITLE}}','Operation Videos').replace('{{LINKS}}',links)
    home=re.sub(r'<div class="video-box">.*?(?=<nav class="video-directory")','',home,count=1,flags=re.S).replace('../brand-logo.png','./brand-logo.png')
    (destination/'index.html').write_text(attach(home,'./'))
    config={'version':version,'pages':['./']+[s+'/' for s,_ in TOPICS], 'assets':['brand-logo.png?v='+logo_version]+[t['cover'] for t in topics if t['cover']], 'videos':[{'url':t['file'],'bytes':t['bytes'],'hash':t['hash']} for t in topics if t['file']]}
    (destination/'sw.js').write_text(worker.replace('__CACHE_CONFIG__',json.dumps(config,separators=(',',':'))))
    (destination/'.nojekyll').touch()
    print('Built 12 pages; '+str(sum(bool(t['file']) for t in topics))+' original videos present. Originals unchanged.')

if __name__ == '__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: python3 build_pages.py --in-place | EMPTY_OUTPUT_DIRECTORY')
    build(ROOT if sys.argv[1]=='--in-place' else Path(sys.argv[1]))
