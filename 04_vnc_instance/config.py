#!/usr/bin/python3

import os
import json

class Config:
    def __init__(self, filename):
        self.filename = filename
        self.data = dict()

    # read config file, return true when success
    def success(self):
        try:
            with open(self.filename) as f:
                self.data = json.load(f)

        except IOError:
            print("Read Config failed")
            return False
        except ValueError:
            print("Invalid Config JSON format")
            return False
        return True

    # load config data
    def load(self):
        return self.data


    
