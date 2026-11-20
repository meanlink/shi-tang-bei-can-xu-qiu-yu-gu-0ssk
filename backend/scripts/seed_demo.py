import time, json
from datetime import date, timedelta
from sqlalchemy import select, func
from src.config.database import Session
from migrations.initial import migrate
from src.models import User, Dataset, Job, Report, Delivery, Audit, SelloutDay, SupplementBatch
from src.services.business import metadata, seed_records, analyze
from src.services.reports import deliver
from src.utils.security import hash_password
from src.utils.serialization import checksum


# 演示用售罄日：落在最后14天回测窗口内，便于直观看到「未报齐不计误差」。
_DEMO_SELLOUTS = [
    {'offset': 101, 'expected_vouchers': 2,
     'supplements': [('PC-20261029-A', 26, '前台候补凭证')]},
    {'offset': 106, 'expected_vouchers': 2,
     'supplements': [('PC-20261103-A', 31, '团体退订后补领'), ('PC-20261103-B', 14, '档口登记补录')]},
]


def _seed_sellouts(db, dataset, admin):
    """幂等登记两个售罄日，一天已报齐、一天仍缺一份凭证。"""
    rows = {row['date']: row for row in dataset.records}
    start = date.fromisoformat(dataset.records[0]['date'])
    for spec in _DEMO_SELLOUTS:
        day = (start + timedelta(days=spec['offset'])).isoformat()
        if day not in rows:
            continue
        entry = db.scalar(select(SelloutDay).where(SelloutDay.dataset_id == dataset.id, SelloutDay.date == day))
        if not entry:
            entry = SelloutDay(dataset_id=dataset.id, date=day, meal=str(rows[day]['meal']),
                               served=float(rows[day]['demand']), expected_vouchers=spec['expected_vouchers'],
                               note='午餐售罄，实领仅计下限', created_by=admin.id, created_at=time.time())
            db.add(entry); db.flush()
            dataset.sellout_revision = (dataset.sellout_revision or 0) + 1
        for voucher, portions, note in spec['supplements']:
            if not db.scalar(select(SupplementBatch).where(SupplementBatch.sellout_id == entry.id, SupplementBatch.voucher_no == voucher)):
                db.add(SupplementBatch(sellout_id=entry.id, voucher_no=voucher, portions=float(portions),
                                       note=note, reported_by=admin.id, created_at=time.time()))
                dataset.sellout_revision = (dataset.sellout_revision or 0) + 1


def seed():
    migrate()
    with Session() as db:
        for role,name in [('admin','林知 · 业务负责人'),('analyst','陈舟 · 分析员'),('viewer','周禾 · 观察员')]:
            email=role+'@demo.local'
            if not db.scalar(select(User).where(User.email==email)):
                db.add(User(email=email,name=name,role=role,password=hash_password('Demo123!')))
        db.flush()
        admin=db.scalar(select(User).where(User.role=='admin'))
        m=metadata()
        d=db.scalar(select(Dataset).where(Dataset.name==m['dataset_name']))
        if not d:
            rows=seed_records()
            d=Dataset(name=m['dataset_name'],source=m['short']+'-202611.csv',records=rows,checksum=checksum(rows),created_at=time.time())
            db.add(d); db.flush()
        _seed_sellouts(db,d,admin)
        db.flush()
        if not db.scalar(select(Job).where(Job.name=='基线复核 · '+m['name'])):
            params={p['key']:p['default'] for p in m.get('parameters',[])}
            from src.services.sellouts import snapshot
            basis={'dataset_checksum':d.checksum,'sellout_revision':d.sellout_revision or 0,
                   'sellouts':snapshot(db,d.id),'frozen_at':time.time()}
            result=analyze(d.records,params,sellouts=basis['sellouts'])
            json.dumps(result,ensure_ascii=False,allow_nan=False)
            j=Job(name='基线复核 · '+m['name'],dataset_id=d.id,params=params,status='completed',result=result,basis=basis,created_by=admin.id,created_at=time.time()-3600,finished_at=time.time()-3595,approved=True)
            db.add(j);db.flush()
            r=Report(name='每日业务复核简报',job_id=j.id,destination='业务复核组 · 本地收件箱',interval_seconds=86400,next_run=time.time()+86400,enabled=True)
            db.add(r);db.flush();deliver(db,r)
            db.add(Audit(actor='seed',action='demo.baseline',detail={'dataset':d.id},at=time.time()))
        db.commit()
        counts={model.__tablename__:db.scalar(select(func.count()).select_from(model)) for model in [User,Dataset,Job,Report,Delivery,Audit,SelloutDay,SupplementBatch]}
        print(json.dumps(counts,ensure_ascii=False))
        return counts
if __name__=='__main__':seed()
