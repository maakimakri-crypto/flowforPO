import os, uuid, hashlib, hmac, secrets, datetime, json
from decimal import Decimal
from pathlib import Path
from contextlib import contextmanager
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import create_engine, text

ROOT=Path(__file__).parent
DB=os.getenv('DATABASE_URL','sqlite:///'+str(ROOT/'data'/'projectflow.db'))
if DB.startswith('postgres://'): DB='postgresql://'+DB[len('postgres://'):]
engine=create_engine(DB,connect_args={'check_same_thread':False} if DB.startswith('sqlite') else {},pool_pre_ping=True)
app=FastAPI(title='ProjectFlow MVP')
app.add_middleware(SessionMiddleware,secret_key=os.getenv('SESSION_SECRET','DEV_ONLY_CHANGE_BEFORE_DEPLOY'),same_site='lax',https_only=os.getenv('COOKIE_SECURE','0')=='1')
app.mount('/static',StaticFiles(directory=str(ROOT/'static')),name='static')

@contextmanager
def conn():
 with engine.begin() as c: yield c

def init():
 with conn() as c:
  for stmt in [
   'CREATE TABLE IF NOT EXISTS users(id VARCHAR(36) PRIMARY KEY, username VARCHAR(100) UNIQUE NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL, role VARCHAR(30) NOT NULL)',
   'CREATE TABLE IF NOT EXISTS projects(id VARCHAR(36) PRIMARY KEY, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE, budget NUMERIC NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT \'EUR\')',
   'CREATE TABLE IF NOT EXISTS pos(id VARCHAR(36) PRIMARY KEY, number TEXT NOT NULL UNIQUE, project_id VARCHAR(36) NOT NULL, supplier TEXT NOT NULL, item TEXT NOT NULL, qty NUMERIC NOT NULL, unit_price NUMERIC NOT NULL, received NUMERIC NOT NULL DEFAULT 0, certified NUMERIC NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT \'Open\', created_at TEXT NOT NULL)',
   'CREATE TABLE IF NOT EXISTS deliveries(id VARCHAR(36) PRIMARY KEY, po_id VARCHAR(36) NOT NULL, qty NUMERIC NOT NULL, note TEXT, created_at TEXT NOT NULL)',
   'CREATE TABLE IF NOT EXISTS certifications(id VARCHAR(36) PRIMARY KEY, po_id VARCHAR(36) NOT NULL, qty NUMERIC NOT NULL, note TEXT, created_at TEXT NOT NULL)',
   'CREATE TABLE IF NOT EXISTS invoices(id VARCHAR(36) PRIMARY KEY, number TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, po_id VARCHAR(36), project_id VARCHAR(36), party TEXT NOT NULL, amount NUMERIC NOT NULL, paid NUMERIC NOT NULL DEFAULT 0, due_date TEXT, status TEXT NOT NULL DEFAULT \'Unpaid\', created_at TEXT NOT NULL)',
   'CREATE TABLE IF NOT EXISTS payments(id VARCHAR(36) PRIMARY KEY, invoice_id VARCHAR(36) NOT NULL, amount NUMERIC NOT NULL, reference TEXT NOT NULL, created_at TEXT NOT NULL)',
   'CREATE TABLE IF NOT EXISTS documents(id VARCHAR(36) PRIMARY KEY, entity_type TEXT NOT NULL, entity_id VARCHAR(36) NOT NULL, original_name TEXT NOT NULL, stored_name TEXT NOT NULL, created_at TEXT NOT NULL)',
   'CREATE TABLE IF NOT EXISTS audit(id VARCHAR(36) PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL)'
  ]: c.execute(text(stmt))
init()

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
def money(v):
 try: d=Decimal(str(v))
 except: raise HTTPException(422,'Invalid number')
 if not d.is_finite(): raise HTTPException(422,'Invalid number')
 return float(d)  # convert to float for SQLite compatibility

def pwd(p,s): return hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),260000).hex()
def user(request):
 u=request.session.get('user')
 if not u: raise HTTPException(401,'Sign in required')
 return u

def permit(request,roles):
 u=user(request)
 if u['role'] not in roles: raise HTTPException(403,'Insufficient permission')
 return u

def audit(c,u,action,entity,id,detail=''):
 c.execute(text('INSERT INTO audit VALUES (:id,:actor,:action,:entity,:eid,:detail,:dt)'),dict(id=uid(),actor=u['username'],action=action,entity=entity,eid=id,detail=detail,dt=now()))

def rows(c,sql,params=None): return [dict(x) for x in c.execute(text(sql),params or {}).mappings().all()]
def bodystr(b,k):
 v=str(b.get(k,'')).strip()
 if not v: raise HTTPException(422,k+' required')
 return v

@app.get('/')
def home(): return FileResponse(ROOT/'static'/'index.html')

@app.get('/api/setup-status')
def setup_status():
 with conn() as c: return {'needs_setup':c.execute(text('SELECT COUNT(*) FROM users')).scalar()==0}

@app.post('/api/setup')
async def setup(req:Request):
 b=await req.json(); username=bodystr(b,'username'); password=bodystr(b,'password')
 if len(password)<12: raise HTTPException(422,'Use at least 12 characters')
 with conn() as c:
  if c.execute(text('SELECT COUNT(*) FROM users')).scalar(): raise HTTPException(403,'Setup already completed')
  s=secrets.token_hex(16)
  c.execute(text('INSERT INTO users VALUES (:id,:u,:p,:s,:r)'),dict(id=uid(),u=username,p=pwd(password,s),s=s,r='admin'))
 return {'ok':True}

@app.post('/api/login')
async def login(req:Request):
 b=await req.json()
 with conn() as c: r=c.execute(text('SELECT * FROM users WHERE username=:u'),{'u':b.get('username','')}).mappings().first()
 if not r or not hmac.compare_digest(r['password_hash'],pwd(str(b.get('password','')),r['salt'])): raise HTTPException(401,'Invalid credentials')
 req.session['user']={'id':r['id'],'username':r['username'],'role':r['role']}
 return {'user':req.session['user']}

@app.post('/api/logout')
def logout(req:Request): req.session.clear();return {'ok':True}
@app.get('/api/me')
def me(req:Request):return user(req)

@app.get('/api/data')
def data(req:Request):
 user(req)
 with conn() as c:
  d={k:rows(c,'SELECT * FROM '+t+' ORDER BY '+order+' DESC') for k,t,order in [('projects','projects','name'),('pos','pos','created_at'),('deliveries','deliveries','created_at'),('certifications','certifications','created_at'),('invoices','invoices','created_at'),('payments','payments','created_at'),('documents','documents','created_at'),('audit','audit','created_at')]}
  d['audit']=d['audit'][:50]
  return d

@app.post('/api/projects')
async def create_project(req:Request):
 u=permit(req,['admin','procurement','manager']); b=await req.json(); name=bodystr(b,'name'); code=bodystr(b,'code'); budget=money(b.get('budget',0))
 if budget<0:raise HTTPException(422,'Budget cannot be negative')
 id=uid()
 with conn() as c:
  if c.execute(text('SELECT 1 FROM projects WHERE code=:code'),{'code':code}).first():raise HTTPException(409,'Project code exists')
  c.execute(text('INSERT INTO projects VALUES (:id,:n,:c,:b,:cur)'),dict(id=id,n=name,c=code,b=budget,cur=b.get('currency','EUR')));audit(c,u,'CREATE','project',id)
 return {'id':id}

@app.post('/api/pos')
async def create_po(req:Request):
 u=permit(req,['admin','procurement']);b=await req.json();qty=money(b.get('qty'));price=money(b.get('unit_price'))
 if qty<=0 or price<0:raise HTTPException(422,'Quantity must be positive and price nonnegative')
 id=uid()
 with conn() as c:
  if not c.execute(text('SELECT 1 FROM projects WHERE id=:id'),{'id':b.get('project_id')}).first():raise HTTPException(422,'Select a project')
  # UUID-derived public number avoids race conditions across simultaneous writers.
  number='PO-'+datetime.datetime.now().strftime('%Y')+'-'+id[:8].upper()
  c.execute(text('INSERT INTO pos(id,number,project_id,supplier,item,qty,unit_price,received,certified,status,created_at) VALUES (:id,:n,:p,:s,:i,:q,:price,0,0,\'Open\',:dt)'),dict(id=id,n=number,p=b['project_id'],s=bodystr(b,'supplier'),i=bodystr(b,'item'),q=qty,price=price,dt=now()))
  audit(c,u,'CREATE','po',id,number)
 return {'id':id,'number':number}

@app.post('/api/deliveries')
async def delivery(req:Request):
 u=permit(req,['admin','store']);b=await req.json();q=money(b.get('qty'));id=uid()
 if q<=0:raise HTTPException(422,'Delivery must be positive')
 with conn() as c:
  r=c.execute(text('SELECT * FROM pos WHERE id=:id'+(' FOR UPDATE' if not DB.startswith('sqlite') else '')),{'id':b.get('po_id')}).mappings().first()
  if not r:raise HTTPException(404,'PO not found')
  updated=c.execute(text('UPDATE pos SET received=received+:q,status=CASE WHEN received+:q>=qty THEN \'Delivered\' ELSE \'Partial\' END WHERE id=:id AND received+:q<=qty'),dict(q=q,id=r['id']))
  if updated.rowcount!=1:raise HTTPException(409,'Delivery exceeds outstanding quantity')
  c.execute(text('INSERT INTO deliveries VALUES (:id,:po,:q,:note,:dt)'),dict(id=id,po=r['id'],q=q,note=b.get('note',''),dt=now()));audit(c,u,'RECEIVE','po',r['id'],str(q))
 return {'id':id}

@app.post('/api/certifications')
async def certify(req:Request):
 u=permit(req,['admin','certifier']);b=await req.json();q=money(b.get('qty'));id=uid()
 if q<=0:raise HTTPException(422,'Certification must be positive')
 with conn() as c:
  r=c.execute(text('SELECT id FROM pos WHERE id=:id'),{'id':b.get('po_id')}).first()
  if not r:raise HTTPException(404,'PO not found')
  updated=c.execute(text('UPDATE pos SET certified=certified+:q WHERE id=:id AND certified+:q<=received'),dict(id=b['po_id'],q=q))
  if updated.rowcount!=1:raise HTTPException(409,'Certification exceeds received quantity')
  c.execute(text('INSERT INTO certifications VALUES (:id,:po,:q,:note,:dt)'),dict(id=id,po=b['po_id'],q=q,note=b.get('note',''),dt=now()));audit(c,u,'CERTIFY','po',b['po_id'],str(q))
 return {'id':id}

@app.post('/api/invoices')
async def invoice(req:Request):
 u=permit(req,['admin','finance']);b=await req.json();kind=b.get('kind');amount=money(b.get('amount'));id=uid()
 if kind not in ['supplier','client']:raise HTTPException(422,'Invalid invoice kind')
 if amount<=0:raise HTTPException(422,'Amount must be positive')
 with conn() as c:
  if kind=='supplier':
   r=c.execute(text('SELECT certified,unit_price FROM pos WHERE id=:id'),{'id':b.get('po_id')}).mappings().first()
   if not r:raise HTTPException(422,'Supplier invoice requires PO')
   prior=money(c.execute(text("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE po_id=:id AND kind='supplier'"),{'id':b['po_id']}).scalar())
   if prior+amount>money(r['certified'])*money(r['unit_price']):raise HTTPException(409,'Invoice exceeds available certified value')
  elif not c.execute(text('SELECT 1 FROM projects WHERE id=:id'),{'id':b.get('project_id')}).first():raise HTTPException(422,'Client invoice requires project')
  num=('BILL-' if kind=='supplier' else 'INV-')+datetime.datetime.now().strftime('%Y')+'-'+id[:8].upper()
  c.execute(text('INSERT INTO invoices VALUES (:id,:num,:kind,:po,:project,:party,:amount,0,:due,\'Unpaid\',:dt)'),dict(id=id,num=num,kind=kind,po=b.get('po_id') if kind=='supplier' else None,project=b.get('project_id') if kind=='client' else None,party=bodystr(b,'party'),amount=amount,due=b.get('due_date',''),dt=now()));audit(c,u,'CREATE','invoice',id,num)
 return {'id':id,'number':num}

@app.post('/api/payments')
async def payment(req:Request):
 u=permit(req,['admin','finance']);b=await req.json();q=money(b.get('amount'));id=uid()
 if q<=0:raise HTTPException(422,'Payment must be positive')
 with conn() as c:
  updated=c.execute(text("UPDATE invoices SET paid=paid+:q,status=CASE WHEN paid+:q>=amount THEN 'Paid' ELSE 'Partially Paid' END WHERE id=:id AND paid+:q<=amount"),dict(id=b.get('invoice_id'),q=q))
  if updated.rowcount!=1:raise HTTPException(409,'Payment exceeds outstanding amount or invoice missing')
  c.execute(text('INSERT INTO payments VALUES (:id,:invoice,:amount,:ref,:dt)'),dict(id=id,invoice=b['invoice_id'],amount=q,ref=bodystr(b,'reference'),dt=now()));audit(c,u,'PAYMENT','invoice',b['invoice_id'],str(q))
 return {'id':id}

@app.post('/api/documents/{entity_type}/{entity_id}')
async def upload(req:Request,entity_type:str,entity_id:str,file:UploadFile=File(...)):
 u=permit(req,['admin','procurement','store','certifier','finance','manager'])
 if entity_type not in ('po','invoice','project'):raise HTTPException(422,'Invalid entity type')
 table={'po':'pos','invoice':'invoices','project':'projects'}[entity_type]
 with conn() as c:
  if not c.execute(text(f'SELECT 1 FROM {table} WHERE id=:id'),{'id':entity_id}).first():raise HTTPException(404,'Record not found')
 content=await file.read(10*1024*1024+1)
 if len(content)>10*1024*1024:raise HTTPException(413,'10 MB limit')
 if not (content.startswith(b'%PDF-') or content.startswith(b'\x89PNG\r\n\x1a\n') or content.startswith(b'\xff\xd8\xff')):raise HTTPException(422,'Only PDF, PNG or JPEG allowed')
 folder=ROOT/'data'/'uploads';folder.mkdir(parents=True,exist_ok=True);id=uid();filename=id+'.bin';(folder/filename).write_bytes(content)
 with conn() as c:
  c.execute(text('INSERT INTO documents VALUES (:id,:type,:eid,:original,:stored,:dt)'),dict(id=id,type=entity_type,eid=entity_id,original=Path(file.filename or 'file').name[:200],stored=filename,dt=now()));audit(c,u,'UPLOAD',entity_type,entity_id,id)
 return {'id':id}

@app.get('/api/documents/{doc_id}')
def download(req:Request,doc_id:str):
 user(req)
 with conn() as c:r=c.execute(text('SELECT * FROM documents WHERE id=:id'),{'id':doc_id}).mappings().first()
 if not r:raise HTTPException(404,'File not found')
 return FileResponse(ROOT/'data'/'uploads'/r['stored'],filename=r['original'])

@app.get('/api/health')
def health():return {'status':'ok'}
