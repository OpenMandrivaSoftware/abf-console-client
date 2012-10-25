import os
import logging
import logging.config

class Log:
    ''' Read the configuration file and create the logging object.'''
    @staticmethod
    def set_verbose():
        logging.getLogger("abf").propagate = 1
        logging.getLogger("abf").handlers[0].setLevel(logging.CRITICAL)
        logging.getLogger("models").propagate = 1
        logging.getLogger("models").handlers[0].setLevel(logging.CRITICAL)
        
    @staticmethod
    def set_quiet():
        logging.getLogger("abf").propagate = 0
        logging.getLogger("models").propagate = 0
        logging.getLogger("abf").handlers[0].setLevel(logging.ERROR)
        logging.getLogger("models").handlers[0].setLevel(logging.ERROR)
    
    @staticmethod
    def set_silent():
        Log.set_verbose()
        logging.getLogger("").handlers[0].setLevel(logging.CRITICAL)
        
    def __init__(self, name=''):
        logging.config.fileConfig(os.path.expanduser('~/.abfcfg'))
        self.log = logging.getLogger(name)
    
    def __getattr__(self, attr):
        return getattr(self.log, attr)