import time, json, logging, uuid
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import Job, Dataset, Report
from src.services.business import analyze
from src.services.reports import deliver
from src.services.audit import record
logging.basicConfig(level=logging.INFO)


def execute(job_id):
    with Session() as db:
        j=db.get(Job,job_id)
        if not j or j.status!='queued':return
        # 每次执行分配独立令牌；提交结果前核对令牌，保证中断重试不重复写入。
        token=uuid.uuid4().hex
        j.status='running'; j.run_token=token; db.commit()
        try:
            d=db.get(Dataset,j.dataset_id)
            basis=j.basis or {}
            # 有冻结依据时，严格按快照计算，绝不用后来补报的数据替换。
            sellouts=basis.get('sellouts') if 'sellouts' in basis else None
            result=analyze(d.records,j.params,sellouts=sellouts)
            json.dumps(result,allow_nan=False)
            db.refresh(j)
            if j.run_token!=token or j.status!='running':
                db.rollback(); return
            j.result=result;j.status='completed';j.finished_at=time.time()
            record(db,'worker','job.completed',{'id':j.id})
        except Exception as e:
            logging.exception('Analysis failed')
            db.rollback()
            db.refresh(j)
            if j.run_token!=token or j.status!='running':
                return
            j.status='failed';j.error=str(e)[:990];j.finished_at=time.time()
            record(db,'worker','job.failed',{'id':j.id,'error':j.error})
        db.commit()
def tick():
    with Session() as db:
        queued=list(db.scalars(select(Job.id).where(Job.status=='queued').limit(3)))
    for job_id in queued:execute(job_id)
    with Session() as db:
        for r in db.scalars(select(Report).where(Report.enabled==True,Report.next_run<=time.time())):
            d=deliver(db,r)
            if d:record(db,'worker','report.delivered',{'id':r.id,'delivery':d.id})
        db.commit()
def main():
    r=Redis.from_url(REDIS_URL,socket_timeout=3)
    # This Compose stack has a single worker. A crash must not strand its jobs.
    with Session() as db:
        for j in db.scalars(select(Job).where(Job.status=='running')):
            j.status='queued';record(db,'worker','job.recovered',{'id':j.id})
        db.commit()
    while True:
        Path('/tmp/heartbeat').touch()
        try:
            item=r.blpop('analysis:queue',timeout=1)
            if item:execute(int(item[1]))
            tick()
        except Exception:
            logging.exception('Worker retry');time.sleep(2)
if __name__=='__main__':main()
