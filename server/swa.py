from werkzeug.wrappers import Request, Response
import json
import traceback
import time
import datetime
from collections import defaultdict
import swa_gen_js
import swa_gen_py

class SimpleWebAPIError(Exception):
    def __init__(self, error_name="SimpleWebAPIError", message="An unknown error occured."):
        self.error_name = error_name
        self.message = message
    def __str__(self):
        return str(self.error_name) + ": " + str(self.message)

class SimpleWebAPI:
    def __init__(self):
        self.api_methods = defaultdict(dict)
        self.default_capability = None
        self.get_capabilities = lambda user: None
        self.check_token = lambda token: None
        self.secure_cookies = False
        self.cookie_location = "/"
        self.cookie_name = "token"
        self.src_cache = {}

        @Request.application
        def application(request):
            if request.method == 'POST' and "application/json" in request.content_type.lower():
                inp = json.loads(request.data.decode('UTF-8'))
                api_version = inp.get("version", 1)
                try:
                    method = inp['method']
                    conf = self.api_methods[method]
                    kwargs = inp.get("kwargs", {});
                    token = None 
                    if "token" in inp:
                        token = inp["token"]
                    elif self.cookie_name in request.cookies:
                        token = request.cookies[self.cookie_name]
                    user = self.check_token(token)
                    capabilities = self.get_capabilities(user)
                    if not capabilities:
                        capabilities = set()
                    details = {
                            "ip":request.remote_addr,
                            "user":user,
                            "capabilities":capabilities,
                            "token":token,
                            "request":request
                            }
                    if conf["details"]:
                        kwargs["details"] = details
                    require = conf["require"]
                    if require == None or require in capabilities:
                        try:
                            call_result = conf["method"](*inp.get("args", []), **kwargs)
                            res = {"success":True,     
                                   "result":call_result}
                        except SimpleWebAPIError as ex:
                            res = {"success":False,
                                   "error":ex.error_name,
                                   "error_message":ex.message}
                        if details["token"] != token:
                            token = details["token"]
                    else:
                        res = {"success":False,
                               "error":"NotAuthorized",
                               "error_message":"The current user cannot call method '" + method + "'."}
                except Exception as ex:
                    traceback.print_exc()
                    res = {"success":False,
                           "error":"Exception",
                           "error_message":"An exception occured while calling method '" + method + "'."}
                if api_version < 2:
                    if res["success"]:
                        res = res["result"]
                    else:
                        res = {"SimpleWebAPIError":res["error"],
                               "Message":res["error_message"]}
                response_object = Response(json.dumps(res))
                if token:
                    response_object.set_cookie(self.cookie_name, token, expires=datetime.datetime.fromtimestamp(time.time()+31557600),httponly=True,secure=self.secure_cookies, path=self.cookie_location)
                return response_object
            elif request.path.endswith("/.js"):
                if "js" not in self.src_cache:
                    self.src_cache["js"] = swa_gen_js.gen_api(self.api_methods, request.url.replace(".js", ""))
                return Response(self.src_cache["js"])
            elif request.path.endswith("/.py"):
                if "py" not in self.src_cache:
                    self.src_cache["py"] = swa_gen_py.gen_api(self.api_methods, request.url.replace(".py", ""))
                return Response(self.src_cache["py"])
            else:
                return Response(json.dumps(list(self.api_methods.keys())))
        
        self.application = application

        @self.add()
        def getMethods():
            return list(self.api_methods.keys())

        @self.add(details=True)
        def getDetails(details):
            return {"capabilities":list(details['capabilities']),
                    "user":details['user']}

        @self.add(details=True)
        def hasCapability(capability, details):
            return capability in details['capabilities']

    def details(self, function):
        """Deprecated decorator to request details."""
        self.api_methods[function.__name__]["details"] = True
        return function

    def add(self, require="DEFAULT_CAP", details=False, name=None):
        """Add a function to the api. (Decorator)
           require: Require a capability to call the function.
           details: Request details of API call, such as user.
           name: Use a different name for the function."""
        # The API used to use this as a "plain" decorator that
        # added the function to the API without any settings.
        if hasattr(require, "__call__"):
            return self.add()(require)

        def add_decorator(function):
            function_name = name or function.__name__
            conf = self.api_methods[function_name]
            conf["method"] = function
            if not "require" in conf:
                if require != "DEFAULT_CAP":
                    conf["require"] = require
                else:
                    conf["require"] = self.default_capability
            if not "details" in conf:
                conf["details"] = details
            return function
        return add_decorator

    def capability(self, require):
        """Deprecated decorator to set capability."""
        def capability_decorator(function):
            self.api_methods[function.__name__]["require"] = require
            return function
        return capability_decorator

    def set_capability_handler(self, function):
        self.get_capabilities = function
        return function

    def set_token_lookup_handler(self, function):
        self.check_token = function
        return function
    def upd_settings(self, settings):
        for key, value in settings.items():
            setattr(self, key, value) 

class ClassAPI:
    def __init__(self):
        self.api_methods = defaultdict(dict)

    def add(self, require="DEFAULT_CAP", details=False, name=None):
        """Stage a method to be added to the API. (Decorator)
           require: Require a capability to call the function.
           details: Request details of API call, such as user.
           name: Use a different name for the function."""

        def add_decorator(function):
            function_name = name or function.__name__
            self.api_methods[function_name] = {"method": function,
                    "require": require,
                    "details": details}
            return function
        return add_decorator

    def commit(self, obj, api):
        for name, conf in self.api_methods.items():
            method = conf["method"].__get__(obj, obj.__class__)
            api.add(require=conf["require"], details=conf["details"], name=name)(method)

