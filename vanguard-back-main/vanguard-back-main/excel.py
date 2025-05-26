import pandas as pd
import re
import Levenshtein
from constants import DISTANCE_RATIO_THRESHOLD
from datetime import datetime
from connector import MYSQLQuery
from io import BytesIO
from constants import DATETIMEFORMAT_READABLE, DATETIMEFORMAT_ISO, REGIONS, EXPORT_CHUNK, IMPORT_CHUNK
from functions import is_date_valid, ph_datetime_now
import mysql.connector

CALO_COLUMNS = ['YEAR_MODEL', 'ASSET_MAKE', 'ASSET_MODEL', 'CHASSIS_SERIAL_NO', 'ENGINE_MOTOR_NUMBER', 'COLLATERAL_DESCRIPTION', 'CS/PLATENO.', 'COLOR', 'Bank', 'Admin']
BRAVO_COLUMNS = ['NO. OF MV', 'NO. OF MC', 'MODES Of LOSS', 'DATE STOLEN', 'TIME STOLEN', 'PLACE STOLEN', 'SPOT REPORT', 'DATE RECOVERED', 'PLACE RECOVERED', 'BLOTTER NUMBER', 'REMARKS']
CHUNKS_SIZE = 100

def get_record_columns() -> dict:
    return {
        'blotter_number': [],
        'mv_file': [],
        'mc_file': [],
        'plate_no': [],
        'engine_no': [],
        'chassis_no': [],
        'district': [],
        'asset_model': [],
        'asset_make': [],
        'asset_year_model': [],
        'color': [],
        'bank': [],
        'mode_of_loss': [],
        'place_stolen': [],
        'datetime_stolen': [],
        'place_recovered': [],
        'datetime_recovered': [],
        'spot_report': [],
        'remarks': [],
    }


def check_data_val(data):
    return data if not pd.isnull(data) and not pd.isna(data) else None


def import_excel_to_db(db_obj: MYSQLQuery, admin_id: int, excel_file: BytesIO, offset: int) -> str:

    print(offset)
    df_xlsx = pd.read_excel(excel_file)
    _df = df_xlsx.iloc[offset * IMPORT_CHUNK : (offset * IMPORT_CHUNK) + IMPORT_CHUNK]
    data = get_record_columns()
    print(_df.shape)
    
    if all(col in _df for col in BRAVO_COLUMNS):
        for index in range(_df.shape[0]):
            index = index + (offset * IMPORT_CHUNK)
            tokens = [token.strip().replace('\n', '').replace('\t', ' ') for token in _df['SPOT REPORT'][index].split(' ') if token.strip() != '' and token.strip() != ' ']
            _report = ' '.join(tokens).replace('NUMBER', 'number')

            def extract_relevant_word(word: str) -> str | None:
                _x = [token for token in tokens if Levenshtein.ratio(word, token.lower()) > DISTANCE_RATIO_THRESHOLD]
                return _x[0] if _x else None

            plate = extract_relevant_word('plate')
            engine = extract_relevant_word('engine')
            chassis = extract_relevant_word('chassis')
            mv_file = extract_relevant_word('mv')
            
            if plate: plate = re.search(r'\b[A-Z0-9][A-Z0-9\-\s]{1,7}[A-Z0-9]\b', _report[_report.find(plate) + len(plate) : _report.find(plate) + 20])
            if engine: engine = re.search(r'\b[A-Z0-9][A-Z0-9\-\s]{6,20}[A-Z0-9]\b', _report[_report.find(engine) + len(engine):])
            if chassis: chassis = re.search(r'\b[A-Z0-9][A-Z0-9\-\s]{6,20}[A-Z0-9]\b', _report[_report.find(chassis) + len(chassis):])
            if mv_file: mv_file = re.search(r'[0-9]{4}(\-|\s)[0-9]+[0-9]\b', _report[_report.find(mv_file) + len(mv_file):])

            data['blotter_number'].append(check_data_val(_df['BLOTTER NUMBER'][index]))
            data['mv_file'].append(mv_file.group() if mv_file else None)
            data['mc_file'].append(check_data_val(_df['NO. OF MC'][index]))
            data['plate_no'].append(plate.group() if plate else None)
            data['engine_no'].append(engine.group() if engine else None)
            data['chassis_no'].append(chassis.group() if chassis else None)
            data['district'].append(check_data_val(_df['DISTRICT'][index]))
            data['asset_model'].append(None)
            data['asset_make'].append(check_data_val(_df['MAKE/TYPE'][index]))
            data['asset_year_model'].append(None)
            data['color'].append(None)
            data['bank'].append(None)
            data['mode_of_loss'].append(check_data_val(_df['MODES Of LOSS'][index]))
            data['place_stolen'].append(check_data_val(_df['PLACE STOLEN'][index]))

            try:
                if check_data_val(_df["DATE STOLEN"][index]) and check_data_val(_df["TIME STOLEN"][index]):
                    datetime_stolen_obj = datetime.strptime(f'{_df["DATE STOLEN"][index]} {_df["TIME STOLEN"][index]}', DATETIMEFORMAT_READABLE)
                    data['datetime_stolen'].append(datetime_stolen_obj.strftime(DATETIMEFORMAT_ISO))
                else: data['datetime_stolen'].append(None)
            except ValueError: data['datetime_stolen'].append(None)


            data['place_recovered'].append(_df['PLACE RECOVERED'][index])
            
            try:
                if check_data_val(_df["DATE RECOVERED"][index]):
                    datetime_recovered_obj = datetime.strptime(f'{_df["DATE RECOVERED"][index]}', '%b %d, %Y')
                    data['datetime_recovered'].append(datetime_recovered_obj.strftime(DATETIMEFORMAT_ISO))
                else: data['datetime_recovered'].append(None)
            except ValueError: data['datetime_recovered'].append(None)

            data['spot_report'].append(check_data_val(_df['SPOT REPORT'][index]))
            data['remarks'].append(check_data_val(_df['REMARKS'][index]))

    elif all(col in _df for col in CALO_COLUMNS):
        for index in range(_df.shape[0]):
            index = index + (offset * IMPORT_CHUNK)

            data['blotter_number'].append(None)
            data['mv_file'].append(None)
            data['mc_file'].append(None)
            data['plate_no'].append(check_data_val(_df['CS/PLATENO.'][index]))
            data['engine_no'].append(check_data_val(_df['ENGINE_MOTOR_NUMBER'][index]))
            data['chassis_no'].append(check_data_val(_df['CHASSIS_SERIAL_NO'][index]))
            data['district'].append(None)
            data['asset_model'].append(check_data_val(_df['ASSET_MODEL'][index]))
            data['asset_make'].append(check_data_val(_df['ASSET_MAKE'][index]))
            data['asset_year_model'].append(check_data_val(_df['YEAR_MODEL'][index]))
            data['color'].append(check_data_val(_df['COLOR'][index]))
            data['bank'].append(check_data_val(_df['Bank'][index]))
            data['mode_of_loss'].append(None)
            data['place_stolen'].append(None)
            data['datetime_stolen'].append(None)
            data['place_recovered'].append(None)
            data['datetime_recovered'].append(None)
            data['spot_report'].append(None)
            data['remarks'].append(None)
    

    elif all(col in _df for col in data.keys()):
        for index in range(_df.shape[0]):
            index = index + (offset * IMPORT_CHUNK)

            data['blotter_number'].append(check_data_val(_df['blotter_number'][index]))
            data['mv_file'].append(check_data_val(_df['mv_file'][index]))
            data['mc_file'].append(check_data_val(_df['mc_file'][index]))
            data['plate_no'].append(check_data_val(_df['plate_no'][index]))
            data['engine_no'].append(check_data_val(_df['engine_no'][index]))
            data['chassis_no'].append(check_data_val(_df['chassis_no'][index]))
            data['district'].append(check_data_val(_df['district'][index]))
            data['asset_model'].append(check_data_val(_df['asset_model'][index]))
            data['asset_make'].append(check_data_val(_df['asset_make'][index]))
            data['asset_year_model'].append(check_data_val(_df['asset_year_model'][index]))
            data['color'].append(check_data_val(_df['color'][index]))
            data['bank'].append(check_data_val(_df['bank'][index]))
            data['mode_of_loss'].append(check_data_val(_df['mode_of_loss'][index]))
            data['place_stolen'].append(check_data_val(_df['place_stolen'][index]))
            
            try:
                if check_data_val(_df["datetime_stolen"][index]):
                    datetime_recovered_obj = datetime.strptime(f'{_df["datetime_stolen"][index]}', DATETIMEFORMAT_READABLE)
                    data['datetime_stolen'].append(datetime_recovered_obj.strftime(DATETIMEFORMAT_ISO))
                else: data['datetime_stolen'].append(None)
            except ValueError: data['datetime_stolen'].append(None)

            data['place_recovered'].append(check_data_val(_df['place_recovered'][index]))

            try:
                if check_data_val(_df["datetime_recovered"][index]):
                    datetime_recovered_obj = datetime.strptime(f'{_df["datetime_recovered"][index]}', DATETIMEFORMAT_READABLE)
                    data['datetime_recovered'].append(datetime_recovered_obj.strftime(DATETIMEFORMAT_ISO))
                else: data['datetime_recovered'].append(None)
            except ValueError: data['datetime_recovered'].append(None)

            data['spot_report'].append(check_data_val(_df['spot_report'][index]))
            data['remarks'].append(check_data_val(_df['remarks'][index]))

    else: return { 'status': 0 }

    err_indices = []
    for i in range(len(data['blotter_number'])):
        try:
            # non remarks columns and values
            vals = []
            for key in data.keys():
                if key != 'remarks':
                    if data[key][i] != None and str(data[key][i]) != 'nan': 
                        if key == 'plate_no' or key == 'engine_no' or key == 'chassis_no': vals.append(re.sub(r'[\-\s]', '', str(data[key][i])))
                        elif key == 'mv_file' or key == 'mc_file': vals.append(re.sub(r'[\s]', '', str(data[key][i])))
                        else: vals.append(str(data[key][i]))
                    else: vals.append(None)
            vals = [v if v != 'nan' else None for v in vals]

            blotter_id = db_obj.create(f'INSERT INTO vanguard_blotters (added_by, date_created, {", ".join([key for key in data.keys() if key != "remarks"])}) VALUES (%s, %s, {", ".join(["%s" for _ in range(len(list(data.keys()))-1)])})', (admin_id, ph_datetime_now(), *vals,), close_conn_on_err=False)

            remarks = data['remarks'][i]
            if str(remarks) != 'nan' and remarks != None:  
                labels = ['Datetime:', 'Region:', 'Officer ID:', 'Officer Name:', 'Remarks:']
                remarks_extracted = []
                for remark in [r.strip() for r in remarks.strip().split('\n\n---\n\n') if r.strip() != '']: 
                    frags = {}
                    split_remark_without_remark = remark.split('\n')[0:4]
                    for i_srwr, r in enumerate(split_remark_without_remark):
                        try:
                            if r[0:len(labels[i_srwr])] == labels[i_srwr]: frags[labels[i_srwr].replace(':', '')] = r.replace(labels[i_srwr], '').strip()
                            else: frags.clear(); break
                        except IndexError: frags.clear; continue

                    find_remark = remark.find('Remarks:', remark.find(split_remark_without_remark[-1]) + len(split_remark_without_remark[-1]))
                    if find_remark != -1: frags[labels[-1].replace(':', '')] = remark[find_remark + len('Remarks:'):].strip()
                    if frags: remarks_extracted.append(frags)
                
                for x_remarks in remarks_extracted:

                    if x_remarks['Region'] not in REGIONS: continue

                    officer_id = None
                    remarks_timestamp = None

                    try: 
                        verify_officer = db_obj.read('SELECT user_id FROM vanguard_users WHERE user_id = %s', (int(x_remarks['Officer ID']),)); 
                        if verify_officer: officer_id = verify_officer[0][0]
                    except Exception: pass
                    
                    try: remarks_timestamp = datetime.strptime(x_remarks['Datetime'], DATETIMEFORMAT_READABLE)
                    except Exception: continue

                    if officer_id: 
                        db_obj.create('INSERT INTO vanguard_blotter_remarks (blotter_id, remarked_by, remarks, region, date_created) VALUES (%s, %s, %s, %s, %s)', (blotter_id, officer_id, x_remarks['Remarks'], x_remarks['Region'], remarks_timestamp.strftime(DATETIMEFORMAT_ISO) if remarks_timestamp else None,), close_conn_on_err=False)

                    else:
                        remarks_as_string = []
                        remarks_as_string.append('Remarks: {0}'.format(x_remarks['Remarks']))
                        remarks_as_string.append('Officer Name: {0}'.format(x_remarks['Officer Name']))
                        remarks_as_string.append('Officer ID: {0}'.format('N/A'))
                        remarks_as_string.append('Datetime: {0}'.format(remarks_timestamp.strftime(DATETIMEFORMAT_READABLE) if remarks_timestamp else 'N/A'))
                        remarks_as_string.append('Region: {0}'.format(x_remarks['Region']))
                        stringify_remark = '\n'.join(remarks_as_string)
                        db_obj.create('INSERT INTO vanguard_blotter_remarks (blotter_id, remarked_by, remarks, region, date_created) VALUES (%s, %s, %s, %s, %s)', (blotter_id, None, stringify_remark, x_remarks['Region'], remarks_timestamp.strftime(DATETIMEFORMAT_ISO) if remarks_timestamp else None,), close_conn_on_err=False)
                        
        except mysql.connector.Error: err_indices.append(i)
    
    return {
        'status': 1
        # 'issue': True if err_indices else False,
        # 'mesage': 'Excel file successfully imported{0}'.format('. However, there\'s an issue with other row/s of the file' if err_indices else '') 
    }




def export_db_to_excel(db_obj: MYSQLQuery, start_date: str, end_date: str, region: str | list, offset: int) -> BytesIO:

    blotter_ids, has_date = [], False
    if start_date != 'null':
        params, date_query = [], '' 

        if type(region) == list: params.extend(region)
        else: params.append(region)

        if is_date_valid(start_date):
            if end_date == 'null': date_query = f'AND DATE(vbr.date_created) = %s'; params.append(start_date)
            else: 
                if is_date_valid(end_date): 
                    if end_date > start_date: date_query = f'AND DATE(vbr.date_created) BETWEEN %s AND %s'; params.extend([start_date, end_date])

            within = db_obj.read(f'SELECT DISTINCT vb.blotter_id, vbr.date_created FROM vanguard_blotters AS vb JOIN vanguard_blotter_remarks AS vbr ON vb.blotter_id = vbr.blotter_id WHERE {"vbr.region IN ({0})".format(", ".join(["%s"] * len(region))) if type(region) == list else "vbr.region = %s"} {date_query} ORDER BY vbr.date_created DESC LIMIT %s OFFSET %s', (*params, EXPORT_CHUNK, offset * EXPORT_CHUNK,))
            blotter_ids = [blotter_id[0] for blotter_id in within]
            has_date = True


    data = get_record_columns()
    blotters = None if has_date and not blotter_ids else db_obj.read(f'SELECT blotter_id, {", ".join([key for key in data.keys() if key != "remarks"])} FROM vanguard_blotters {"WHERE blotter_id IN ({0})".format(", ".join(["%s"] * len(blotter_ids))) if has_date else ""} ORDER BY date_created DESC {"" if has_date else "LIMIT %s OFFSET %s"}', (*(blotter_ids if has_date else ()), *(() if has_date else [EXPORT_CHUNK, offset * EXPORT_CHUNK,])))
    if blotters: 
        for blotter in blotters: 
            blotter = blotter[1:]
            for index, key in enumerate([key for key in data.keys() if key != 'remarks']): 
                if key == 'datetime_stolen' or key == 'datetime_recovered': data[key].append(blotter[index].strftime(DATETIMEFORMAT_READABLE) if blotter[index] else None)
                else: data[key].append(blotter[index])
        
        for blotter in blotters:
            blotter_id = blotter[0]
            remarks = db_obj.read('SELECT vbr.date_created, vbr.region, vbr.remarked_by, vu.name, vbr.remarks FROM vanguard_blotter_remarks AS vbr JOIN vanguard_users AS vu ON vbr.remarked_by = vu.user_id WHERE vbr.blotter_id = %s ORDER BY vbr.date_created DESC', (blotter_id,))
            _f_remarks = []
            for remark in remarks:
                if remark[2] == None: _f_remarks.append(remark[4])
                else:
                    remarks_frags = []
                    remarks_frags.append(f'Datetime: {remark[0].strftime(DATETIMEFORMAT_READABLE)}'.strip())
                    remarks_frags.append(f'Region: {remark[1]}'.strip())
                    remarks_frags.append(f'Officer ID: {remark[2]}'.strip())
                    remarks_frags.append(f'Officer Name: {remark[3]}'.strip())
                    remarks_frags.append(f'Remarks: {remark[4]}'.strip())
                    _f_remarks.append('\n'.join(remarks_frags))

            if _f_remarks: data['remarks'].append('\n\n---\n\n'.join(_f_remarks))
            else: data['remarks'].append(None)

    _excel_df = pd.DataFrame(data)
    excel_bytes = BytesIO()
    _excel_df.to_excel(excel_bytes, index=False)
    excel_bytes.seek(0)

    return excel_bytes