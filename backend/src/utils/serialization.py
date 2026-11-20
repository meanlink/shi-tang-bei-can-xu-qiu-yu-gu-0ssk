import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    dates=sorted(row.get('date','') for row in (d.records or []) if row.get('date'))
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'sellout_revision':d.sellout_revision or 0, 'first_date':dates[0] if dates else '', 'last_date':dates[-1] if dates else '', 'created_at':d.created_at}
def job_dict(j, dataset=None):
    data={k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
    basis=j.basis or {}
    data['basis']={k:basis.get(k) for k in ['dataset_checksum','sellout_revision','frozen_at']}
    data['basis']['sellout_count']=len(basis.get('sellouts',[]))
    data['basis']['incomplete_sellouts']=sum(1 for s in basis.get('sellouts',[]) if not s.get('complete'))
    data['stale']=None
    if dataset is not None and basis:
        stale=[]
        if basis.get('dataset_checksum') and basis['dataset_checksum']!=dataset.checksum:
            stale.append('数据批次内容已变化')
        if basis.get('sellout_revision') is not None and basis['sellout_revision']!=(dataset.sellout_revision or 0):
            stale.append('售罄登记或补报已更新')
        data['stale']=bool(stale)
        data['stale_reasons']=stale
    return data
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
