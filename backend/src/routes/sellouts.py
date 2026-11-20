from fastapi import APIRouter, Depends, HTTPException
from src.config.database import get_db
from src.middlewares.auth import current_user, can_write
from src.schemas.sellout import SelloutInput, SupplementInput
from src.services import sellouts
router = APIRouter()


@router.get('/datasets/{dataset_id}/sellouts')
def listing(dataset_id: int, db=Depends(get_db), u=Depends(current_user)):
    return sellouts.list_for_dataset(db, dataset_id)


@router.post('/datasets/{dataset_id}/sellouts', status_code=201)
def register(dataset_id: int, data: SelloutInput, db=Depends(get_db), u=Depends(can_write)):
    entry = sellouts.register(db, dataset_id, data, u)
    db.commit()
    return entry


@router.post('/sellouts/{sellout_id}/supplements', status_code=201)
def supplement(sellout_id: int, data: SupplementInput, db=Depends(get_db), u=Depends(can_write)):
    entry = sellouts.report_supplement(db, sellout_id, data, u)
    db.commit()
    return entry
