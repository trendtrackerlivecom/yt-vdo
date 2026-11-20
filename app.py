import os, re, uuid, time, threading, subprocess, shutil
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, send_file, abort
import yt_dlp

app=Flask(__name__)
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'downloads'; OUT.mkdir(exist_ok=True)
JOBS={}; LOCK=threading.Lock()
MAX_ACTIVE=int(os.getenv('MAX_ACTIVE','2'))
MAX_DURATION=int(os.getenv('MAX_DURATION','7200'))
MAX_BYTES=int(os.getenv('MAX_BYTES',str(3*1024**3)))
QUALITY={144,240,360,480,720,1080,1440,2160}
# Enable Node.js for yt-dlp's YouTube JavaScript challenge solver.
# The bgutil script provider (its server is built into the Docker image)
# generates PO Tokens so YouTube accepts requests from cloud IPs, and
# source_address forces IPv4 — YouTube often returns an empty player
# response to cloud IPv6 ranges ("Failed to extract any player response").
BGUTIL_SERVER_HOME=os.getenv('BGUTIL_SERVER_HOME','/opt/bgutil/server')
YTDLP_JS={'js_runtimes': {'node': {}},'extractor_args': {'youtubepot-bgutilscript': {'server_home': [BGUTIL_SERVER_HOME]}},'source_address': '0.0.0.0'}

def valid_url(url):
    try:
        p=urlparse(url)
        host=(p.hostname or '').lower()
        return p.scheme=='https' and host in {'youtube.com','www.youtube.com','m.youtube.com','youtu.be','www.youtu.be','youtube-nocookie.com','www.youtube-nocookie.com'} and len(url)<2048 and not p.username and not p.password
    except Exception:return False

def probe(path):
    p=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type','-of','default=noprint_wrappers=1:nokey=1',str(path)],capture_output=True,text=True,timeout=30)
    return p.returncode==0 and 'video' in p.stdout.splitlines() and 'audio' in p.stdout.splitlines()

def clean():
    while True:
        time.sleep(600)
        cutoff=time.time()-3600
        with LOCK:
            for jid,j in list(JOBS.items()):
                if j.get('finished_at',float('inf'))<cutoff:
                    shutil.rmtree(OUT/jid,ignore_errors=True); JOBS.pop(jid,None)
threading.Thread(target=clean,daemon=True).start()

@app.get('/')
def index():return render_template('index.html')

@app.post('/api/info')
def info():
    url=(request.get_json(silent=True) or {}).get('url','').strip()
    if not valid_url(url):return jsonify(error='Enter a valid YouTube video HTTPS URL.'),400
    try:
        with yt_dlp.YoutubeDL({'quiet':True,'no_warnings':True,'noplaylist':True,'skip_download':True,'socket_timeout':15,'extract_flat':False,**YTDLP_JS}) as y:
            d=y.extract_info(url,download=False)
        if d.get('_type')=='playlist':return jsonify(error='Only individual videos are supported.'),400
        if (d.get('duration') or 0)>MAX_DURATION:return jsonify(error='Video is too long for this server.'),400
        heights=sorted({f.get('height') for f in d.get('formats',[]) if f.get('height') in QUALITY})
        return jsonify(title=d.get('title','Video'),duration=d.get('duration'),thumbnail=d.get('thumbnail'),qualities=heights)
    except Exception as e:return jsonify(error=f'Could not analyze video: {str(e)[:250]}'),422

def worker(jid,url,quality,fmt):
    folder=OUT/jid
    def progress(d):
        if d['status']=='downloading':
            total=d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            if total>MAX_BYTES:raise RuntimeError('Download exceeds server size limit')
            with LOCK:JOBS[jid].update(status='downloading',percent=round(d.get('downloaded_bytes',0)*100/total,1) if total else 0,speed=d.get('_speed_str',''))
        elif d['status']=='finished':
            with LOCK:JOBS[jid].update(status='processing',percent=100)
    try:
        folder.mkdir(exist_ok=True)
        opts={'format':f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]', 'outtmpl':str(folder/'%(title).100B-%(id)s.%(ext)s'),'noplaylist':True,'quiet':True,'no_warnings':True,'progress_hooks':[progress],'merge_output_format':'mkv','max_filesize':MAX_BYTES,'socket_timeout':20,'retries':3,'fragment_retries':3,'restrictfilenames':True,**YTDLP_JS}
        with yt_dlp.YoutubeDL(opts) as y:y.download([url])
        candidates=[p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {'.mkv','.mp4','.webm','.mov','.3gp'}]
        if not candidates:raise RuntimeError('No video output produced')
        src=max(candidates,key=lambda p:p.stat().st_size)
        if fmt=='mkv' and src.suffix.lower()=='.mkv':dest=src
        else:
            dest=folder/f'YT-VDO-{jid[:8]}.{fmt}'
            if fmt=='mp4':cmd=['ffmpeg','-y','-i',str(src),'-map','0:v:0','-map','0:a:0','-c:v','libx264','-preset','veryfast','-crf','23','-c:a','aac','-b:a','160k','-movflags','+faststart',str(dest)]
            elif fmt=='3gp':cmd=['ffmpeg','-y','-i',str(src),'-map','0:v:0','-map','0:a:0','-vf','scale=352:288:force_original_aspect_ratio=decrease,pad=352:288:(ow-iw)/2:(oh-ih)/2','-r','15','-c:v','h263','-b:v','350k','-c:a','aac','-ar','22050','-ac','1','-b:a','48k',str(dest)]
            else:cmd=['ffmpeg','-y','-i',str(src),'-map','0:v:0','-map','0:a:0','-c','copy',str(dest)]
            with LOCK:JOBS[jid]['status']='processing'
            r=subprocess.run(cmd,capture_output=True,text=True,timeout=3600)
            if r.returncode:raise RuntimeError('FFmpeg conversion failed: '+r.stderr[-350:])
        if not probe(dest):raise RuntimeError('Output does not contain both video and audio streams')
        for p in folder.iterdir():
            if p!=dest and p.is_file():p.unlink(missing_ok=True)
        with LOCK:JOBS[jid].update(status='done',percent=100,file=dest.name,finished_at=time.time())
    except Exception as e:
        with LOCK:JOBS[jid].update(status='error',error=str(e)[:350],finished_at=time.time())

@app.post('/api/download')
def download():
    data=request.get_json(silent=True) or {}; url=str(data.get('url','')).strip(); fmt=data.get('format'); quality=data.get('quality')
    try:quality=int(quality)
    except (TypeError,ValueError):quality=0
    if not valid_url(url) or fmt not in {'mp4','mkv','3gp'} or quality not in QUALITY:return jsonify(error='Invalid download settings'),400
    with LOCK:
        if sum(j['status'] not in {'done','error'} for j in JOBS.values())>=MAX_ACTIVE:return jsonify(error='Server busy. Try again shortly.'),429
        jid=uuid.uuid4().hex; JOBS[jid]={'status':'queued','percent':0,'created_at':time.time()}
    threading.Thread(target=worker,args=(jid,url,quality,fmt),daemon=True).start()
    return jsonify(id=jid),202

@app.get('/api/status/<jid>')
def status(jid):
    with LOCK:j=JOBS.get(jid); return (jsonify(j) if j else (jsonify(error='Job not found'),404))

@app.get('/api/file/<jid>')
def file(jid):
    with LOCK:j=JOBS.get(jid)
    if not j or j.get('status')!='done':abort(404)
    p=OUT/jid/j['file']
    if not p.is_file():abort(404)
    return send_file(p,as_attachment=True,download_name=p.name)

if __name__=='__main__':app.run(host='127.0.0.1',port=5000)
