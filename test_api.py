import urllib.request
import urllib.parse
import mimetypes
import uuid
import json

url = "http://localhost:8000/analyze"
file_path = "dummy_form.pdf"
boundary = str(uuid.uuid4())

data = []
data.append(f'--{boundary}')
data.append(f'Content-Disposition: form-data; name="file"; filename="{file_path}"')
data.append('Content-Type: application/pdf')
data.append('')
with open(file_path, 'rb') as f:
    data.append(f.read().decode('latin1')) # simple decoding for binary
data.append(f'--{boundary}--')
data.append('')

body = '\r\n'.join(data).encode('latin1')
headers = {'Content-Type': f'multipart/form-data; boundary={boundary}'}

req = urllib.request.Request(url, data=body, headers=headers)

try:
    with urllib.request.urlopen(req) as response:
        result = json.load(response)
        print("Success!")
        print(f"Filename: {result.get('filename')}")
        print(f"Fields found: {len(result.get('fields', []))}")
        # print first few fields
        for f in result.get('fields', [])[:3]:
            print(f" - {f.get('name')} ({f.get('type')})")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(e.read().decode())
except Exception as e:
    print(f"Error: {e}")
