import re
import Levenshtein
import os
from google.cloud import vision
from PIL import Image
from io import BytesIO
from datetime import datetime
from uuid import uuid4
from connector import MYSQLQuery
import json
from functions import ph_datetime_now

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'requires/vanguard-vision-key.json'

def google_vision(image_file, db_obj: MYSQLQuery, user_id: int) -> list:

    try:
        identifier = []
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_file)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        
        if (texts[0].description):
            result_string = [fx for fx in ' '.join([t.strip() for t in texts[0].description.split('\n')]).split(' ')]
            res = ' '.join([rs for rs in result_string if Levenshtein.ratio(rs.lower(), 'temporary') < 0.9 and Levenshtein.ratio(rs.lower(), 'registered') < 0.9 and Levenshtein.ratio(rs.lower(), 'region') < 0.9])

            find_mv = list(re.finditer(r'\b[0-9]{4}(\s\-\s|\s|\-)[0-9]+[0-9]\b', res.upper()))
            if find_mv: identifier.append(['mv_file', [re.sub(r'[\s]', '', x.group()) for x in find_mv]])

            prefix_letter_plate = list(re.finditer(r'\b[A-Z][A-Z0-9]{1,2}[\-\s]?[0-9]{3,5}\b', res.upper()))
            if prefix_letter_plate: identifier.append(['plate_no', [re.sub(r'[\-\s]', '', x.group()) for x in prefix_letter_plate]])

            prefix_number_plate = list(re.finditer(r'\b[0-9]{3}[\-\s]?[A-Z0-9]{3}\b', res.upper()))
            if prefix_number_plate: identifier.append(['plate_no', [re.sub(r'[\-\s]', '', x.group()) for x in prefix_number_plate]])

            # img = Image.open(BytesIO(image_file))
            # now = datetime.now().date().strftime('%Y-%m-%d')

            # if (not os.path.exists(f'ocr_images/{now}')): os.mkdir(f'ocr_images/{now}')
            # img.save(f'ocr_images/{now}/{uuid4()}.{img.format.lower()}')

            # db_obj.create('INSERT INTO vanguard_ocr_requests (requested_by, filename, result, requested_at) VALUES (%s, %s, %s, %s)', (user_id, f'/{now}/{uuid4()}.{img.format.lower()}', json.dumps(identifier), ph_datetime_now()))

        return identifier
    except Exception: return []
    



# def apnr_long_distance(image_file) -> list | None:
#     img = cv2.imread(image_file)
#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     bfilter = cv2.bilateralFilter(gray, 11, 17, 17)

#     edged = cv2.Canny(bfilter, 30, 200)

#     keypoints = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
#     contours = imutils.grab_contours(keypoints) 
#     contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

#     location = None
#     for contour in contours:
#         approx = cv2.approxPolyDP(contour, 10, True)
#         if len(approx) == 4:
#             location = approx
#             break

#     if not location: return None    
    
#     mask = np.zeros(gray.shape, np.uint8) 
#     cv2.drawContours(mask, [location], 0, 255, -1) 
#     cv2.bitwise_and(img, img, mask=mask) 

#     (x,y) = np.where(mask==255) 
#     (x1, y1) = (np.min(x), np.min(y)) 
#     (x2, y2) = (np.max(x), np.max(y)) 
#     cropped_image = gray[x1:x2+1, y1:y2+1]

#     reader = easyocr.Reader(['en']) 
#     result = reader.readtext(cropped_image) 
#     return result



# def apnr_short_distance(image_file) -> list:
#     resize_image = cv2.resize(image_file, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
#     gray = cv2.cvtColor(resize_image, cv2.COLOR_BGR2GRAY)
#     bfilter = cv2.bilateralFilter(gray, 11, 17, 17)

#     reader = easyocr.Reader(['en']) 
#     result = reader.readtext(bfilter) 

#     res = ''
#     for r in result:
#         if Levenshtein.ratio(r[1].lower(), 'temporary') < 0.9 and Levenshtein.ratio(r[1].lower(), 'registered') < 0.9 and Levenshtein.ratio(r[1].lower(), 'region') < 0.9:
#             res += r[1] + ' '

#     identifier = []
#     find_mv = list(re.finditer(r'\b[0-9]{4}(\s\-\s|\s|\-)[0-9]+[0-9]\b', res.upper()))
#     if find_mv: identifier = ['mv_file', [re.sub(r'[\s]', '', x.group()) for x in find_mv]]
#     else:
#         prefix_letter_plate = list(re.finditer(r'\b[A-Z][A-Z0-9]{1,2}[\-\s]?[0-9]{3,5}\b', res.upper()))
#         if prefix_letter_plate: identifier = ['plate_no', [re.sub(r'[\-\s]', '', x.group()) for x in prefix_letter_plate]]
#         else:
#             prefix_number_plate = list(re.finditer(r'\b[0-9]{3}[\-\s]?[A-Z0-9]{3}\b', res.upper()))
#             if prefix_number_plate: identifier = ['plate_no', [re.sub(r'[\-\s]', '', x.group()) for x in prefix_number_plate]]

#     print(identifier)
#     print(res)
#     return identifier





        