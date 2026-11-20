"""售罄日登记与按凭证补报未领份数。

售罄（卖光）当天的实领份数只是真实需求的下限。计划组按凭证分批补报未领份数，
报齐后才把「实领 + 未领」作为真实需求参与误差计算。补报会推进数据批次的
``sellout_revision``，据此让仍引用旧依据的分析任务失去批准资格。
"""
import math
import time

from fastapi import HTTPException
from sqlalchemy import select

from src.models import Dataset, SelloutDay, SupplementBatch
from src.services.audit import record


def _sellout_payload(db, day):
    vouchers = list(db.scalars(select(SupplementBatch).where(SupplementBatch.sellout_id == day.id).order_by(SupplementBatch.id)))
    reported = float(sum(v.portions for v in vouchers))
    lower = float(day.served)
    complete = len(vouchers) >= day.expected_vouchers
    return {
        'id': day.id, 'dataset_id': day.dataset_id, 'date': day.date, 'meal': day.meal,
        'served': round(lower, 2), 'lower_bound': round(lower, 2),
        'expected_vouchers': day.expected_vouchers, 'voucher_count': len(vouchers),
        'reported_supplement': round(reported, 2),
        'demand_lower_bound': round(lower, 2),
        'adjusted_demand': round(lower + reported, 2) if complete else None,
        'complete': complete, 'open_vouchers': max(0, day.expected_vouchers - len(vouchers)),
        'note': day.note, 'created_at': day.created_at,
        'vouchers': [{'id': v.id, 'voucher_no': v.voucher_no, 'portions': v.portions,
                      'note': v.note, 'created_at': v.created_at} for v in vouchers],
    }


def list_for_dataset(db, dataset_id):
    if not db.get(Dataset, dataset_id):
        raise HTTPException(404, '数据批次不存在')
    days = db.scalars(select(SelloutDay).where(SelloutDay.dataset_id == dataset_id).order_by(SelloutDay.date))
    return [_sellout_payload(db, day) for day in days]


def snapshot(db, dataset_id):
    """冻结当前售罄状态，供分析任务在创建时保存为不可变依据。"""
    snap = []
    for day in db.scalars(select(SelloutDay).where(SelloutDay.dataset_id == dataset_id).order_by(SelloutDay.date)):
        payload = _sellout_payload(db, day)
        snap.append({
            'date': payload['date'], 'served': payload['served'],
            'reported': payload['reported_supplement'], 'complete': payload['complete'],
            'expected_vouchers': payload['expected_vouchers'], 'voucher_count': payload['voucher_count'],
            'vouchers': [v['voucher_no'] for v in payload['vouchers']],
        })
    return snap


def register(db, dataset_id, data, user):
    dataset = db.scalars(select(Dataset).where(Dataset.id == dataset_id).with_for_update()).first()
    if not dataset:
        raise HTTPException(404, '数据批次不存在')
    try:
        from datetime import date
        day = date.fromisoformat(str(data.date))
    except (TypeError, ValueError):
        raise HTTPException(422, '售罄日期须为YYYY-MM-DD')
    rows = {row['date']: row for row in dataset.records}
    record_row = rows.get(day.isoformat())
    if not record_row:
        raise HTTPException(422, '该日期不在所选数据批次中，请先导入当日记录')
    served = float(record_row['demand'])
    if served < 0 or not math.isfinite(served):
        raise HTTPException(422, '当日实领份数无效，无法登记售罄')
    if data.served is not None and abs(float(data.served) - served) > 1e-9:
        raise HTTPException(409, f'当日批次实领为 {served:g} 份，与提交的 {float(data.served):g} 份不一致')
    if db.scalar(select(SelloutDay).where(SelloutDay.dataset_id == dataset_id, SelloutDay.date == day.isoformat())):
        raise HTTPException(409, '该售罄日已登记，可继续补报凭证')
    entry = SelloutDay(dataset_id=dataset_id, date=day.isoformat(), meal=str(record_row['meal']),
                       served=served, expected_vouchers=data.expected_vouchers,
                       note=(data.note or '').strip(), created_by=user.id, created_at=time.time())
    db.add(entry)
    dataset.sellout_revision = (dataset.sellout_revision or 0) + 1
    record(db, user.email, 'sellout.register', {'dataset': dataset_id, 'date': day.isoformat(), 'served': served})
    db.flush()
    return _sellout_payload(db, entry)


def report_supplement(db, sellout_id, data, user):
    entry = db.scalars(select(SelloutDay).where(SelloutDay.id == sellout_id).with_for_update()).first()
    if not entry:
        raise HTTPException(404, '售罄日不存在')
    dataset = db.scalars(select(Dataset).where(Dataset.id == entry.dataset_id).with_for_update()).first()
    voucher = (data.voucher_no or '').strip()
    if not voucher:
        raise HTTPException(422, '凭证号不能为空')
    try:
        portions = float(data.portions)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(422, '未领份数须为有效数值')
    if not math.isfinite(portions) or portions < 0:
        raise HTTPException(422, '未领份数须为非负有限数')
    existing = db.scalar(select(SupplementBatch).where(SupplementBatch.sellout_id == sellout_id, SupplementBatch.voucher_no == voucher))
    if existing:
        # 同一凭证重试：不重复入账，原样返回既有记录。
        if abs(float(existing.portions) - portions) > 1e-9:
            raise HTTPException(409, f'凭证 {voucher} 已按 {existing.portions:g} 份登记，不能改为 {portions:g} 份')
        payload = _sellout_payload(db, entry)
        payload['duplicate'] = True
        return payload
    if len(list(db.scalars(select(SupplementBatch.id).where(SupplementBatch.sellout_id == sellout_id)))) >= entry.expected_vouchers:
        raise HTTPException(409, '该售罄日凭证已报齐，如份数有误请联系负责人重新登记')
    batch = SupplementBatch(sellout_id=sellout_id, voucher_no=voucher, portions=portions,
                            note=(data.note or '').strip(), reported_by=user.id, created_at=time.time())
    db.add(batch)
    dataset.sellout_revision = (dataset.sellout_revision or 0) + 1
    record(db, user.email, 'sellout.supplement', {'sellout': sellout_id, 'date': entry.date, 'voucher': voucher, 'portions': portions})
    db.flush()
    payload = _sellout_payload(db, entry)
    payload['duplicate'] = False
    return payload
