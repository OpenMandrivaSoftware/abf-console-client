import ConfigParser
import os
from abf.console.misc import mkdirs, ask_user

#####################################################
# USAGE:
#
# from abf.console.config import Config
# 
# cfg = Config()
# cfg['aaa']['bbb'] = 'ccc'
# print cfg['aaa']['bbb']
# print cfg['aaa'].pop('bbb')
# print cfg.pop('aaa')
#####################################################

class Section(dict):
    def __init__(self, config, conf_path, section):
        self.section = section
        self.config = config
        self.conf_path = conf_path
        if not section in self.config.sections():
            self.config.add_section(self.section)
            self.save()
            
    def save(self):
        with open(self.conf_path, 'wb') as configfile:
            self.config.write(configfile)
            
    def __setitem__(self, key, value):
        '''NOTE: value is ignored'''
        if key in self and self[key] == value:
            return
        super(Section, self).__setitem__(key, value)
        self.config.set(self.section, key, value)
        self.save()
            
    def __getitem__(self, key):
        if super(Section, self).__contains__(key):
            return super(Section, self).__getitem__(key)
        res = self.config.get(section, opt)
        
    def pop(self, key, init=None):
        if init is not None and key not in self:
            return init
        res = super(Section, self).pop(key, init)
        
        self.config.remove_option(self.section, key)
        self.save()
        return res
            
class Config(dict):
    default_url = 'https://abf.rosalinux.ru'
    default_log_path = '/var/log/abf.log'
    def __init__(self, conf_path='~/.abfcfg'):
        self.conf_path = os.path.expanduser(conf_path)
        init = False
        if not os.path.isfile(self.conf_path):
            mkdirs(os.path.dirname(self.conf_path))
            init = True
        
        self.config = ConfigParser.RawConfigParser()
        self.config.read(self.conf_path)

        sections = self.config.sections()
        for section in sections:
            self[section] = []
            opts = self.config.options(section)
            for opt in opts:
                self[section][opt] = self.config.get(section, opt)
        
        if init:
            self.first_start()
        

    def __setitem__(self, key, value):
        '''NOTE: value is ignored'''
        if super(Config, self).__contains__(key):
            return
        super(Config, self).__setitem__(key, Section(self.config, self.conf_path, key))
            
    def __getitem__(self, key):
        if not super(Config, self).__contains__(key):
            self[key] = []
        return super(Config, self).__getitem__(key)
        
    def pop(self, section, init=None):
        if init is not None and section not in self:
            return init
        res = super(Config, self).pop(section, init)
        self.config.remove_section(section) 
        res.save()
        return res
          
    def first_start(self):
        print("First start")
        #self['main'] = []
        #self['user'] = []

        done = False
        while not done:
            domain = ask_user('ABF domain [%s]:' % Config.default_url, can_be_empty=True)
            domain = domain or Config.default_url
            if domain and domain.endswith('/'):
                domain = domain[:-1] # remove trailing '/'
            parts = domain.split('//')
            if len(parts) == 1:
                print 'No protocol part specified (http://, https://, etc.)'
                continue         
            if len(parts) > 2:
                print 'Double slashe must present only once (in a ptocol part)'
                continue
            done = True
        
        self['main']['domain'] = domain
        
        user = ask_user('User:', can_be_empty=False)
        self['user']['login'] = user
        
        password = ask_user('Password:', can_be_empty=False)
        self['user']['password'] = password
        
        git_uri = "%(protocol)s//%(user)s@%(domain)s" % \
                dict(protocol=parts[0], user=user, domain=parts[1])
        
        self['user']['git_uri'] = git_uri
        
        res = ask_user('Default group [%s]:' % user, can_be_empty=True)
        self['user']['default_group'] = res or user
        
        #configure logging       
        self['formatters']['keys'] = 'verbose,simple'
        self['formatter_verbose']['format'] = '%(asctime)s %(levelname)-7s in %(filename)s:%(funcName)s:%(lineno)d: %(message)s'
        self['formatter_simple']['format'] = '%(message)s'
        
        self['loggers']['keys'] = 'root,abf,beaker'
        self['logger_root']['handlers'] = 'verbose'
        self['logger_root']['propagate'] = '1'
        self['logger_root']['level'] = 'DEBUG'
        self['logger_root']['qualname'] = ''
        self['logger_abf']['handlers'] = 'main'
        self['logger_abf']['propagate'] = '0'
        self['logger_abf']['level'] = 'DEBUG'
        self['logger_abf']['qualname'] = 'abf'
        self['logger_models']['handlers'] = 'main'
        self['logger_models']['propagate'] = '0'
        self['logger_models']['level'] = 'DEBUG'
        self['logger_models']['qualname'] = 'models'
        
        self['logger_beaker']['handlers'] = 'verbose'
        self['logger_beaker']['propagate'] = '1'
        self['logger_beaker']['level'] = 'ERROR'
        self['logger_beaker']['qualname'] = 'beaker'
        
        self['handlers']['keys'] = 'verbose,main'
        self['handler_verbose']['level'] = 'DEBUG'
        self['handler_verbose']['class'] = 'StreamHandler'
        self['handler_verbose']['formatter'] = 'verbose'
        self['handler_verbose']['args'] = '()'
        self['handler_main']['level'] = 'WARNING'
        self['handler_main']['class'] = 'StreamHandler'
        self['handler_main']['formatter'] = 'simple'
        self['handler_main']['args'] = '()'
        
        print('Initial configuration have been completed')
        exit()

        
        
        

        