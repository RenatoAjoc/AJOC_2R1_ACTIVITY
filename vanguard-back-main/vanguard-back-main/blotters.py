from excel import get_record_columns
from constants import DATETIMEFORMAT_READABLE
from errors import http_server_err
from connector import MYSQLQuery

def blotters_in_ids(db_obj: MYSQLQuery, blotter_ids: list):

    cols = get_record_columns()
    blotters = []
    if blotter_ids:
        blotter_record = db_obj.read('SELECT blotter_id, {0} FROM vanguard_blotters WHERE del = 0 AND blotter_id IN ({1})'.format(', '.join([col for col in cols.keys() if col != 'remarks']), ', '.join(['%s'] * len(blotter_ids))), (*blotter_ids,))
        if not blotter_record: raise http_server_err('Record doesn\'t exists or removed')
        for blotter in blotter_record:
            bltr = blotter[1:]
            blotters.append({col: bltr[i] if bltr[i] != None else '' for i, col in enumerate(col for col in cols.keys() if col != 'remarks')})

            remarks = db_obj.read('SELECT vbr.date_created, vbr.region, vbr.remarked_by, vu.name, vbr.remarks, vbr.remarks_id FROM vanguard_blotter_remarks AS vbr JOIN vanguard_users AS vu ON vbr.remarked_by = vu.user_id WHERE vbr.blotter_id = %s ORDER BY vbr.date_created ASC', (blotter[0],))
            remarks_frags = []
            for remark in remarks:
                remarks_frags.append({
                    'remarks_id': remark[5],
                    'datetime': remark[0].strftime(DATETIMEFORMAT_READABLE),
                    'region': remark[1],
                    'officer_name': remark[3],
                    'remarks': remark[4]
                })

            blotters[-1]['remarks'] = remarks_frags
            blotters[-1]['blotter_id'] = blotter[0]
            
    return blotters