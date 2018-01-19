
'''
--------------------
import requests
requests.post('https://textbelt.com/text', {
  'phone': '5557727420',
  'message': 'Hello world',
  'key': 'textbelt',
})

$ curl -X POST https://textbelt.com/text \
       --data-urlencode phone='5557727420' \
       --data-urlencode message='Hello world' \
       -d key=textbelt
{"success":true,"textId":"2861516228856794","quotaRemaining":249}[jdn@jdnLinux teslawatch]$

$ curl https://textbelt.com/status/2861516228856794
{"success":true,"status":"DELIVERED"}
'''
