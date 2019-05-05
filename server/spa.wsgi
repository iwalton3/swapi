#!/usr/bin/env python3
from swa import SimpleWebAPI
from email_session_manager import EmailSessionManager
from sqlalchemy import create_engine
import json

conf = json.load(open("/etc/swa-conf.json"))

api = SimpleWebAPI()
api.upd_settings(conf["api"])
database = create_engine(conf["database"], pool_recycle=3600)
sessionManager = EmailSessionManager(api, database)
sessionManager.upd_settings(conf["session"])

import app
app.init(api)

application = api.application

