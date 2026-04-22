import requests
import uuid
import time
import json

api_url = 'https://sx17qwedz7.apigw.ntruss.com/custom/v1/37154/5ca6687105b044bda966c909ce90086ca659389fd480b305a09d43a0aa1d8ba9/general'
secret_key = 'bkZBWEl6U2dtb3pmeUpqZGhWWlZqb1ZQU3JnU3VLRk4='

def request_ocr(image_file):
	try:
		request_json = {
		    'images': [
		        {
		            'format': 'jpg',
		            'name': 'demo'
		        }
		    ],
		    'requestId': str(uuid.uuid4()),
		    'version': 'V2',
		    'timestamp': int(round(time.time() * 1000))
		}

		payload = {'message': json.dumps(request_json).encode('UTF-8')}
		files = [
		  ('file', open(image_file,'rb'))
		]
		headers = {
		  'X-OCR-SECRET': secret_key
		}

		response = requests.request("POST", api_url, headers=headers, data = payload, files = files)
		return response
	except Exception as ex:
		print(str(ex))

if __name__=="__main__":
	image_file = 'c:/temp/file.png'

	response = request_ocr(image_file)
	# 원래 코드는 print(response.text.encode('utf8'))이지만 수정
	for i in response.json()['images'][0]['fields']:
	    text = i['inferText']
	    print(text)
	print(response.text)
