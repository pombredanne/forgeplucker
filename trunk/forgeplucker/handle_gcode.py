
import sys, os, re, time, calendar
from htmlscrape import *
from generic import *

class GCode(GenericForge):
    "Handler class for Google code"
    def login(self, username, password):
        response = GenericForge.login(self, {
            'Email':username,
            'Passwd':password,
            'PersistentCookie':'yes',
            'rmShown':'1',
            'dsh':'-5632636127808727784',
            'GALX':'vyqwe0uqoJ0',
            'asts':'',
            'signIn':'Sign In'},
            "Sign Out")
    def login_url(self):
        return "https://www.google.com/accounts/LoginAuth"
