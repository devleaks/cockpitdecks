# pip install requests
import requests

DATA = "data"
IDENT = "id"
INDEX = "index"
NAME = "name"
DURATION = "duration"
VALUE = "value"


API_URL = "http://192.168.1.140:8080/api"


response = requests.get(f"{API_URL}/v2/datarefs")
cache = response.json()
cache_by_name = {d["name"]: d for d in cache["data"]}

dataref = "sim/network/dataout/data_to_screen"
drefmodel = cache_by_name[dataref]
print(drefmodel)

# read value
value_url = f"{API_URL}/v2/datarefs/{drefmodel['id']}/value"
response = requests.get(value_url)
result = response.json()
value = result["data"]
print(value)

# change a value for demo
x = value[20]
print(value[20])
x = 0 if x == 1 else 1
value[20] = x
print(value[20])

# Try to update entire array: OK
payload = {DATA: value}
print("payload", payload)
response = requests.patch(value_url, json=payload)
print(response)

# Try to update entire one value: not OK
value_url = value_url + f"?index={20}"
payload = {DATA: x}
print("payload", value_url, payload)
response = requests.patch(value_url, json=payload)
print(response, response.text)
