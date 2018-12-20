# swapi

This is an **experimental** system that combines RPC and React to create web applications. It allows you to write web applications in Python and then call those functions from a front-end written in React. The system supports an email-based session manager and capability system, which allows you to identify users and require certain capabilities for users to be able to call functions.

## Building

You need a working installation of nodejs to compile the web application. Run `build.sh` from the project directory to download the dependencies and build the project.

The server is a WSGI server, which you can add to apache using a directive like this:

```
WSGIDaemonProcess spa-api user=www-data group=www-data processes=2 threads=5
WSGIScriptAlias /spa-api /var/lib/pyapis/spa.wsgi process-group=spa-api application-group=%{GLOBAL}
```

For the server to work, you need to install these packages:

```
apt install mysql-server python3-pymysql python3-sqlalchemy python3-werkzeug
```

You will also need to setup a mailgun account to send email. The configuration for mailgun, user roles, and the database are stored in `/etc/swa-conf.json`. An example configuration, which you will need to edit, has been provided. The `app.py.example` file contains some example functions, add your own and install the module.
