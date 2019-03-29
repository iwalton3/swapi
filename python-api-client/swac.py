import json
import urllib.request

class api:
    def __init__(self, url, token=None):
        self.url = url
        self.token = token
        self.gen_methods()

    def _call_method(self, method, *args, **kwargs):
        call = {"method":method,
                    "args":args,
                    "kwargs":kwargs}
        if (self.token != None):
            call["token"] = self.token
        request = urllib.request.Request(self.url,
                data=json.dumps(call).encode('utf8'),
                headers={"Content-Type":"application/json"},
                method="POST")
        return json.loads(urllib.request.urlopen(request).read().decode('utf-8'))

    def _register_method(self, method_name):
        def method_wrapper(*args, **kwargs):
            nonlocal method_name
            return self._call_method(method_name, *args, **kwargs)
        setattr(self, method_name, method_wrapper)

    def gen_methods(self):
        methods = self._call_method("getMethods")
        for method in methods:
            self._register_method(method)



