from constants import JWT_SETTINGS, REQ_LIMIT, DATETIMEFORMAT_READABLE, DATETIMEFORMAT_ISO, REGIONS, EXPORT_CHUNK, IMPORT_CHUNK
from datetime import datetime, timedelta, timezone
from typing import Annotated, List
from fastapi import Depends, FastAPI, HTTPException, status, WebSocket, WebSocketException, WebSocketDisconnect, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from auth import ws_user, authenticate_user, create_access_token, rest_user, pwd_context
from connector import MYSQLQuery, vdbpool
from sockets import ws_manager
from errors import http_auth_err, http_server_err
from vision import google_vision
from excel import import_excel_to_db, export_db_to_excel, get_record_columns
import numpy as np
import re
from io import BytesIO
from functions import is_datetime_valid, list_val_at, flatten_list, stringify_and, stringify_or, is_readable_datetime_valid, is_date_valid, ph_datetime_now
from blotters import blotters_in_ids
import math
import pandas as pd

app = FastAPI(version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# @app.websocket('/ws/{room}/{token}')
# async def websocket_endpoint(websocket: WebSocket, room: str, token: str):
#     await websocket.accept()
#     try:
#         db_obj = MYSQLQuery(igisdbpool)
#         validate_user = ws_user(token)
#         if not validate_user: await websocket.close(); return

#         if room != 'null':
#             vr = validate_room(db_obj, validate_user['id'], room, DB_ERR_WS)
#             del db_obj
#             if not vr: await websocket.close(); return
        
#         await ws_manager.connect(websocket, validate_user['user_uuid'], validate_user['id'], vr['room'] if room != 'null' else None, vr['room_type'] if room != 'null' else None)
#         await ws_manager.message(websocket, 'join', f'{validate_user["username"]} joined the chat')
        
#         while True:
            
#             data = await websocket.receive_json()
#             if not data or type(data) != dict: continue
#             if not data.get('type'): continue

#             if (data['type'] == 'chat'): print(data)

#     except WebSocketDisconnect as wsd:
#         await ws_manager.disconnect(websocket)

#     except RuntimeError as rterr:
#         await websocket.close()
#         await ws_manager.disconnect(websocket)


@app.get('/')
async def test():
    return {
        'message': 'Working'
    }



class ObtainToken(BaseModel):
    identifier: str
    password: str


@app.post("/token")
async def login_for_access_token(req: ObtainToken):
    user = authenticate_user(req.identifier, req.password)
    if not user: raise http_auth_err('Incorrect identifier or password')
    access_token_expires = timedelta(days=JWT_SETTINGS['access_token_expire_days'])
    access_token = create_access_token(data={ 'sub': user['username'] }, expires_delta=access_token_expires)
    return {
        'access_token': access_token, 
        'token_type': 'bearer',
        'user': {
            'user_role': user['role']
        }
    }




class Registration(BaseModel):
    username: str
    password: str
    name: str
    email: str
    branch_address: str
    region: str

@app.post('/register')
async def register(current_user: Annotated[str, Depends(rest_user)], req: Registration):

    if (current_user['role'] != 'Admin'): raise http_auth_err('Unauthorized!');

    db_obj = MYSQLQuery(vdbpool)
    verify_username = db_obj.read('SELECT user_id FROM vanguard_users WHERE username = %s', (req.username,))
    if verify_username: raise http_server_err('Username already exists')

    verify_email = db_obj.read('SELECT email FROM vanguard_users WHERE username = %s', (req.email,))
    if verify_email: raise http_server_err('Email already exists')

    if (not bool(re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', req.email))): raise http_server_err('Email is not valid')

    if (req.region not in REGIONS): raise http_server_err('Invalid region')

    db_obj.create('INSERT INTO vanguard_users (username, password, name, email, role, branch_address, region, date_created) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', (req.username, pwd_context.hash(req.password), req.name, req.email, 'HPG Officer', req.branch_address, req.region, ph_datetime_now(),))
    
    return {
        'message': 'User created'
    }


@app.post('/ocr')
async def ocr(current_user: Annotated[str, Depends(rest_user)], image: Annotated[UploadFile, File()]):
    if image.content_type.find('image') == -1: raise http_server_err('Not an image file')
    try: 
        db_obj = MYSQLQuery(vdbpool)
        image_file_bytes = await image.read()
        ocr_content = google_vision(image_file_bytes, db_obj, current_user['id'])
        
        if ocr_content:
            db_obj = MYSQLQuery(vdbpool)
            fquery, fparams = [], []

            for result in ocr_content:
                nums_query = []
                for nums in result[1]:
                    nums_query.append(f'UPPER({result[0]}) {"LIKE" if result[0] == "mv_file" else "="} UPPER(%s)')
                    fparams.append(f'%{nums}%' if result[0] == "mv_file" else nums)
                fquery.append(stringify_or(nums_query))

            record = db_obj.read(f'SELECT blotter_id FROM vanguard_blotters WHERE del = 0 AND {stringify_or(fquery)} ORDER BY date_created DESC', (*fparams,))
                
            if record: return {
                # 'blotters': [bid[0] for bid in record],
                # 'offset': 0,
                'message': f'Has {len(record)} matching report. Please check the details',
                'count': len(record),
                'result': ocr_content,
                'status': 1
            }
            else: return {
                'message': 'Has no matching report. Also try manual to be certain',
                'result': ocr_content,
                'status': 0
            }
        else: return {
            'message': 'Please try to capture the plate again or use manual',
            'status': 2
        }
    except Exception: raise http_server_err()



class ManualSearch(BaseModel):
    query: str

@app.post('/manual')
async def manual(current_user: Annotated[str, Depends(rest_user)], req: ManualSearch):
    db_obj = MYSQLQuery(vdbpool)
    
    if req.query == '': raise http_server_err('Empty query')
    blotter_ids = db_obj.read('SELECT blotter_id FROM vanguard_blotters WHERE del = 0 AND (UPPER(mv_file) LIKE UPPER(%s) OR UPPER(mc_file) LIKE UPPER(%s) OR UPPER(plate_no) = UPPER(%s) OR UPPER(engine_no) = UPPER(%s) OR UPPER(chassis_no) = UPPER(%s))', (*[req.query for _ in range(5)],))
    if not blotter_ids: return {
        'message': 'Has no matching report',
        'status': 0,
    }

    return {
        # 'blotters': [bid[0] for bid in blotter_ids],
        # 'offset': 0,
        'message': f'Has {len(blotter_ids)} matching report/s. Please check the details',
        'status': 1,
        'count': len(blotter_ids),
    }




class ResultObjects(BaseModel):
    offset: int
    basis: str | list

@app.post('/blotter-scan-results')
async def blotter_scan_results(current_user: Annotated[str, Depends(rest_user)], req: ResultObjects):

    db_obj = MYSQLQuery(vdbpool)
    record = []
    if type(req.basis) == list:
        fquery, fparams = [], []
        for result in req.basis:
            nums_query = []
            for nums in result[1]:
                nums_query.append(f'UPPER({result[0]}) {"LIKE" if result[0] == "mv_file" else "="} UPPER(%s)')
                fparams.append(f'%{nums}%' if result[0] == "mv_file" else nums)
            fquery.append(stringify_or(nums_query))

        record = db_obj.read(f'SELECT blotter_id FROM vanguard_blotters WHERE del = 0 AND {stringify_or(fquery)} ORDER BY date_created DESC LIMIT %s OFFSET %s', (*fparams, REQ_LIMIT, req.offset,))

    else:
        if req.basis == '': raise http_server_err('Empty query')
        record = db_obj.read('SELECT blotter_id FROM vanguard_blotters WHERE del = 0 AND (UPPER(mv_file) LIKE UPPER(%s) OR UPPER(mc_file) LIKE UPPER(%s) OR UPPER(plate_no) = UPPER(%s) OR UPPER(engine_no) = UPPER(%s) OR UPPER(chassis_no) = UPPER(%s)) LIMIT %s OFFSET %s', (*[req.basis for _ in range(5)], REQ_LIMIT, req.offset,))

    if record:
        _blotters = db_obj.read(f'SELECT blotter_id, blotter_number, district, mc_file, mv_file, plate_no, chassis_no, engine_no FROM vanguard_blotters WHERE del = 0 AND blotter_id IN ({", ".join(["%s"] * len(record))}) ORDER BY blotter_id DESC', (*[bid[0] for bid in record],))
        return {
            'data': [{ 
                'blotter_id': x[0], 
                'blotter_number': x[1],
                'district': x[2], 
                'mc_file': x[3], 
                'mv_file': x[4], 
                'plate': x[5], 
                'chassis': x[6], 
                'engine': x[7] 
            } for x in _blotters],
            'offset': req.offset + REQ_LIMIT if len(_blotters) == REQ_LIMIT else -1
        }

    return {
        'data': [],
        'offset': -1
    }




@app.post('/import-excel')
async def import_excel(current_user: Annotated[str, Depends(rest_user)], excel: Annotated[UploadFile, File()], offset: Annotated[str, Form()]):
    if (current_user['role'] != 'Admin'): raise http_auth_err('Not authorized')
    if excel.content_type != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': raise http_server_err('Not an excel file')

    try:
        int_offset = int(offset)
    except ValueError: http_server_err('Offset must be a number')

    db_obj = MYSQLQuery(vdbpool)
    excel_file_bytes = await excel.read()
    imports = import_excel_to_db(db_obj, current_user['id'], BytesIO(excel_file_bytes), int_offset)
    return {
        'data': imports
    }



@app.post('/check-import-size')
async def import_excel(current_user: Annotated[str, Depends(rest_user)], excel: Annotated[UploadFile, File()]):
    if (current_user['role'] != 'Admin'): raise http_auth_err('Not authorized')
    if excel.content_type != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': raise http_server_err('Not an excel file')
    
    try:
        df_xlsx = pd.read_excel(BytesIO(await excel.read()))
        parts = math.ceil(df_xlsx.shape[0] / IMPORT_CHUNK)

        if parts == 0: return { 'parts': -1 }
        else: return { 'parts': parts }

    except Exception: raise http_server_err()





@app.get('/export-excel/{start_date}/{end_date}/{region}/{offset}')
async def export_excel(current_user: Annotated[str, Depends(rest_user)], start_date: str, end_date: str, region: str, offset: int):
    if (current_user['role'] != 'Admin'): raise http_auth_err('Not authorized')
    try: 
        region_list = [r.strip() for r in region.split(',')]
        if region != 'null': 
            if False in [False if r not in REGIONS else True for r in region_list]: raise http_server_err('Invalid region')

        db_obj = MYSQLQuery(vdbpool)
        excel_file = export_db_to_excel(db_obj, start_date, end_date, region_list if region != 'null' else current_user['region'], offset)
        now = datetime.now().strftime(DATETIMEFORMAT_ISO)
        now = re.sub(r'[\s\:]', '-', now)
        return Response(content=excel_file.getvalue(), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={"Content-Disposition": f"attachment;filename=blotters-exported-excel-[{now}]-[part-{offset+1}].xlsx"})
    except Exception: raise http_server_err()



class CheckExportSizeObjects(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    region: list | None = None


@app.post('/check-export-size')
async def check_export_size(current_user: Annotated[str, Depends(rest_user)], req: CheckExportSizeObjects):
    if (current_user['role'] != 'Admin'): raise http_auth_err('Not authorized')

    db_obj = MYSQLQuery(vdbpool)
    all_blotter_size = []

    if req.start_date:
        params, date_query = [], '' 
        
        if req.region: params.extend(req.region)
        else: params.append(current_user['region'])

        if is_date_valid(req.start_date):
            if not req.end_date: date_query = f'AND DATE(vbr.date_created) = %s'; params.append(req.start_date)
            else: 
                if is_date_valid(req.end_date): 
                    if req.end_date > req.start_date: date_query = f'AND DATE(vbr.date_created) BETWEEN %s AND %s'; params.extend([req.start_date, req.end_date])

            all_blotter_size = db_obj.read(f'SELECT DISTINCT COUNT(*) FROM vanguard_blotters AS vb JOIN vanguard_blotter_remarks AS vbr ON vb.blotter_id = vbr.blotter_id WHERE {"vbr.region IN ({0})".format(", ".join(["%s"] * len(req.region))) if req.region else "vbr.region = %s"} {date_query} ORDER BY vbr.date_created DESC', params)

    else: all_blotter_size = db_obj.read('SELECT COUNT(*) FROM vanguard_blotters')

    parts = math.ceil(all_blotter_size[0][0]/ EXPORT_CHUNK)
    
    if parts == 0: return { 'parts': -1 }
    elif parts == 1: return { 'parts': parts }
    else: return { 'parts': parts, 'size_per_part': EXPORT_CHUNK }
        
    



@app.get('/filters')
async def filters(current_user: Annotated[str, Depends(rest_user)]):
    
    if (current_user['role'] != 'Admin'): raise http_auth_err('Not authorized')

    db_obj = MYSQLQuery(vdbpool)
    _districts = db_obj.read('SELECT DISTINCT district FROM vanguard_blotters WHERE del = 0 AND district IS NOT NULL')
    _colors = db_obj.read('SELECT DISTINCT color FROM vanguard_blotters WHERE del = 0 AND color IS NOT NULL')
    _asset_makes = db_obj.read('SELECT DISTINCT asset_make FROM vanguard_blotters WHERE del = 0 AND asset_make IS NOT NULL')

    return {
        'data': {
            'districts': [{ 'value': d[0] } for d in _districts],
            'colors': [{ 'value': c[0] } for c in _colors],
            'asset_makes': [{ 'value': a[0] } for a in _asset_makes]
        }
    }


class Blotters(BaseModel):
    offset: int
    query: str | None = None
    district: list | None = None
    color: list | None = None
    make: list | None = None
    has_spot_report: bool | None = None
    date_stolen: list | None = None

@app.post('/blotters')
async def blotters(current_user: Annotated[str, Depends(rest_user)], req: Blotters):
    if (current_user['role'] != 'Admin'): raise http_auth_err('Not authorized')

    db_obj = MYSQLQuery(vdbpool)
    fquery, fparams = [], []

    if req.district: fquery.append('district IN ({0})'.format(', '.join(['%s'] * len(req.district)))); fparams.extend(req.district)
    if req.color: fquery.append('color IN ({0})'.format(', '.join(['%s'] * len(req.color)))); fparams.extend(req.color)
    if req.make: fquery.append('asset_make IN ({0})'.format(', '.join(['%s'] * len(req.make)))); fparams.extend(req.make)
    if req.has_spot_report != None: fquery.append('spot_report IS NOT NULL' if req.has_spot_report else 'spot_report IS NULL')

    if req.date_stolen and len(req.date_stolen) == 2:
        if is_datetime_valid(req.date_stolen[0]) and is_datetime_valid(req.date_stolen[1]): fquery.append('(datetime_stolen BETWEEN %s AND %s)'); fparams.extend(req.date_stolen)

    if req.query: fquery.append('(blotter_number LIKE %s OR mv_file LIKE %s OR mc_file LIKE %s OR plate_no LIKE %s OR engine_no LIKE %s OR chassis_no LIKE %s)'); fparams.extend([f'%{req.query}%'] * 6)

    fquery_and = stringify_and(fquery)
    filter_const = f'AND {fquery_and}' if fquery_and else ''

    _blotters = db_obj.read(f'SELECT blotter_id, blotter_number, district, mc_file, mv_file, plate_no, chassis_no, engine_no FROM vanguard_blotters WHERE del = 0 {filter_const} ORDER BY blotter_id DESC LIMIT %s OFFSET %s', (*fparams, REQ_LIMIT, req.offset,))

    return {
        'data': [{ 
            'blotter_id': x[0], 
            'blotter_number': x[1],
            'district': x[2], 
            'mc_file': x[3], 
            'mv_file': x[4], 
            'plate': x[5], 
            'chassis': x[6], 
            'engine': x[7] 
        } for x in _blotters],
        'offset': req.offset + REQ_LIMIT if len(_blotters) == REQ_LIMIT else -1
    }


@app.get('/blotter/{blotter_id}')
async def blotter(current_user: Annotated[str, Depends(rest_user)], blotter_id: int):
    db_obj = MYSQLQuery(vdbpool)
    return {
        'data': blotters_in_ids(db_obj, [blotter_id])
    }


class BlotterUpdate(BaseModel):
    blotter_id: int
    blotter_number: str
    mv_file: str
    mc_file: str
    plate_no: str
    engine_no: str
    chassis_no: str
    district: str
    asset_model: str
    asset_make: str
    asset_year_model: str
    color: str
    bank: str
    mode_of_loss: str
    place_stolen: str
    datetime_stolen: str
    place_recovered: str
    datetime_recovered: str
    spot_report: str
    remarks: list


@app.post('/blotter-record-update')
async def blotter_record_update(current_user: Annotated[str, Depends(rest_user)], req: BlotterUpdate):
    if (current_user['role'] != 'Admin'): raise http_auth_err('Not authorized')
    db_obj = MYSQLQuery(vdbpool)
    cols = get_record_columns()

    datetime_stolen = req.datetime_stolen
    datetime_recovered = req.datetime_recovered

    if datetime_stolen:
        if is_readable_datetime_valid(datetime_stolen):
            datetime_stolen = datetime.strptime(datetime_stolen, DATETIMEFORMAT_READABLE).strftime(DATETIMEFORMAT_ISO)  
        else: raise http_server_err('Update unsuccessful: The provided date is in an invalid format. Please ensure the date is formatted as follows: ex. Jan 01, 2024 10:00 PM.')

    if datetime_recovered:
        if is_readable_datetime_valid(datetime_recovered):
            datetime_recovered = datetime.strptime(datetime_recovered, DATETIMEFORMAT_READABLE).strftime(DATETIMEFORMAT_ISO)  
        else: raise http_server_err('Update unsuccessful: The provided date is in an invalid format. Please ensure the date is formatted as follows: ex. Jan 01, 2024 10:00 PM.')

    params = (
        req.blotter_number if req.blotter_number else None, 
        req.mv_file if re.sub(r'[\s]', '', req.mv_file) else None, 
        req.mc_file if re.sub(r'[\s]', '', req.mc_file) else None, 
        req.plate_no if req.plate_no else None, 
        req.engine_no if req.engine_no else None,
        req.chassis_no if req.chassis_no else None, 
        req.district if req.district else None, 
        req.asset_model if req.asset_model else None, 
        req.asset_make if req.asset_make else None, 
        req.asset_year_model if req.asset_year_model else None, 
        req.color if req.color else None, 
        req.bank if req.bank else None, 
        req.mode_of_loss if req.mode_of_loss else None, 
        req.place_stolen if req.place_stolen else None, 
        datetime_stolen if datetime_stolen else None, 
        req.place_recovered if req.place_recovered else None, 
        datetime_recovered if datetime_recovered else None, 
        req.spot_report if req.spot_report else None, 
        req.blotter_id,
    )
    db_obj.update('UPDATE vanguard_blotters SET {0} WHERE blotter_id = %s'.format(', '.join(['{0} = %s'.format(key) for key in cols.keys() if key != 'remarks'])), params)
    
    for remark in req.remarks:
        db_obj.update('UPDATE vanguard_blotter_remarks SET remarks = %s WHERE remarks_id = %s', (remark['remarks'], remark['remarks_id']))

    return {
        'message': 'Blotter record updated successfully'
    }
    

@app.delete('/reset-records')
async def reset_records(current_user: Annotated[str, Depends(rest_user)]):
    if (current_user['role'] != 'Admin'): raise http_auth_err('Not authorized')
    db_obj = MYSQLQuery(vdbpool)

    db_obj.update('SET FOREIGN_KEY_CHECKS = 0')
    db_obj.update('TRUNCATE TABLE vanguard_blotter_remarks')
    db_obj.update('TRUNCATE TABLE vanguard_blotters')
    db_obj.update('SET FOREIGN_KEY_CHECKS = 1')

    return {
        'message': 'The records have been cleared'
    }



class AddRemarks(BaseModel):
    blotter_id: int
    remarks: str
    place_recovered: str | None = None
    datetime_recovered: str | None = None

@app.post('/add-remarks')
async def reset_records(current_user: Annotated[str, Depends(rest_user)], req: AddRemarks):
    db_obj = MYSQLQuery(vdbpool)

    recovered = False
    has_date = db_obj.read('SELECT place_recovered, datetime_recovered FROM vanguard_blotters WHERE blotter_id = %s LIMIT 1', (req.blotter_id,))
    if not has_date[0][0] and not has_date[0][1]:
        if req.datetime_recovered and req.place_recovered:
            if is_readable_datetime_valid(req.datetime_recovered): 
                datetime_recovered = datetime.strptime(req.datetime_recovered, DATETIMEFORMAT_READABLE)
                db_obj.create('UPDATE vanguard_blotters SET place_recovered = %s, datetime_recovered = %s WHERE blotter_id = %s', (req.place_recovered, datetime_recovered, req.blotter_id,))
                recovered = True
            else: raise http_server_err('date recovered has invalid format')

    now = ph_datetime_now()
    remark_id = db_obj.create('INSERT INTO vanguard_blotter_remarks (blotter_id, remarked_by, remarks, region, date_created) VALUES (%s, %s, %s, %s, %s)', (req.blotter_id, current_user['id'], req.remarks, current_user['region'], now,))
    
    return {
        'message': 'Successfully added remarks',
        'recovered': recovered,
        'data': {
            'remarks_id': remark_id,
            'datetime': datetime.strptime(now, DATETIMEFORMAT_ISO).strftime(DATETIMEFORMAT_READABLE),
            'region': current_user['region'],
            'officer_name': current_user['name'],
            'remarks': req.remarks
        }
    }