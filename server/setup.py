from setuptools import setup
import os

setup(
    name='swapi',
    version='1.0.0',
    author="Izzie Walton",
    author_email="iwalton3@gmail.com",
    description="New template for making applications on iwalton.com.",
    license='LGPLv3',
    url="https://github.com/iwalton3/swapi",
    py_modules=['swa', 'email_session_manager', 'swa_gen_py', 'swa_gen_js'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=['pymysql', 'sqlalchemy', 'werkzeug']
)

