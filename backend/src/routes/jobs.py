from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Dataset, Job
from src.schemas.job import JobInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import jobs
from src.services.audit import record
from src.utils.serialization import job_dict
router=APIRouter(prefix='/jobs')
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    datasets={d.id:d for d in db.scalars(select(Dataset))}
    return [job_dict(j,datasets.get(j.dataset_id)) for j in db.scalars(select(Job).order_by(Job.id.desc()).limit(100))]
@router.post('',status_code=201)
def create(data:JobInput,db=Depends(get_db),u=Depends(can_write)):
    j=jobs.create(db,data,u); record(db,u.email,'job.create',{'id':j.id,'params':j.params})
    db.commit(); jobs.enqueue(j.id); return job_dict(j,db.get(Dataset,j.dataset_id))
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    return job_dict(j,db.get(Dataset,j.dataset_id))
@router.post('/{id}/approve')
def approve(id:int,db=Depends(get_db),u=Depends(admin_only)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    if j.status!='completed':raise HTTPException(409,'仅已完成结果可以批准')
    # 与补报并发：锁住数据批次再核对依据版本，旧依据不能获得批准。
    dataset=db.scalars(select(Dataset).where(Dataset.id==j.dataset_id).with_for_update()).first()
    basis=j.basis or {}
    if basis:
        if basis.get('dataset_checksum') and dataset and basis['dataset_checksum']!=dataset.checksum:
            raise HTTPException(409,'数据批次内容已变化，请基于最新批次重新计算后再批准')
        if basis.get('sellout_revision') is not None and basis['sellout_revision']!=(dataset.sellout_revision or 0):
            raise HTTPException(409,'该结果依据的售罄登记已更新，请基于最新补报重新计算后再批准')
    j.approved=True; record(db,u.email,'job.approve',{'id':id}); db.commit()
    return job_dict(j,dataset)
