#!/usr/bin/env python3
from swa import SimpleWebAPI, EmailSessionManager
from sqlalchemy import create_engine
import json

conf = json.load(open("/etc/swa-conf.json"))

api = SimpleWebAPI()
api.default_capability = conf["default_capability"]
database = create_engine(conf["database"], pool_recycle=3600)

sessionManager = EmailSessionManager(api, database)
sessionManager.upd_settings(conf["settings"])

import app
app.init(api)

application = api.application

