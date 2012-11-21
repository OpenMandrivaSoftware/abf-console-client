import ConfigParser
import os
import sys
import getpass

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

VERSION = 3

def mkdirs(path):
    ''' the equivalent of mkdir -p path'''
    if os.path.exists(path):
        return
    path = os.path.normpath(path)
    items = path.split('/')
    p = ''
    for item in items:
        p += '/' + item
        if not os.path.isdir(p):
            os.mkdir(p)
            
def ask_user(prompt, can_be_empty=False, variants=None):
    while True:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        res = sys.stdin.readline()
        res = res.strip()
        if not can_be_empty and not res:
            continue
        
        if variants:
            if res in variants:
                break
            else:
                continue
        break
        
    return res

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
        try:
            res = self.config.get(self.section, key)
        except ConfigParser.NoOptionError, ex:
            print 'error in config "%s": %s' % (self.conf_path, str(ex))
            exit(1)
        
    def pop(self, key, init=None):
        if init is not None and key not in self:
            return init
        res = super(Section, self).pop(key, init)
        
        self.config.remove_option(self.section, key)
        self.save()
        return res
            
class Config(dict):
    default_url = 'https://abf.rosalinux.ru'
    default_filestore_url = 'http://file-store.rosalinux.ru'
    default_log_path = '/var/log/abf.log'
    def __init__(self, conf_path='~/.abfcfg', main_conf=True):
        self.conf_path = os.path.expanduser(conf_path)
        self.main_conf = main_conf
        init = False
        if not os.path.isfile(self.conf_path):
            mkdirs(os.path.dirname(self.conf_path))
            init = True
            
        
        self.config = ConfigParser.RawConfigParser()
        self.config.read(self.conf_path)

        sections = self.config.sections()
        for section in sections:
            opts = self.config.options(section)
            for opt in opts:
                super(Section, self[section]).__setitem__(opt, self.config.get(section, opt))
                

        if main_conf and ('config_version' not in self['main'] or int(self['main']['config_version']) != VERSION):
            print "Sorry, but configuration schema have been changed or config file have been corrupted, so you need to reinitialize the configuration."
            init = True
            
        if init and main_conf:
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
          
    def ask_user_url(self, prompt, default):
        done = False
        while not done:
            domain = ask_user(prompt, can_be_empty=True)
            domain = domain or default
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
        return domain
          
    def first_start(self):
        
        domain = self.ask_user_url('ABF URL [%s]: ' % Config.default_url, Config.default_url)
        self['main']['abf_url'] = domain
        
        user_default = getpass.getuser()
        user = ask_user('User [%s]: ' % user_default, can_be_empty=True)
        self['user']['login'] = user or user_default
        
        #password = ask_user('Password: ', can_be_empty=False)
        password = getpass.getpass()
        self['user']['password'] = password
        
        parts = domain.split('//')
        git_uri = "%(protocol)s//%(user)s@%(domain)s" % \
                dict(protocol=parts[0], user=user, domain=parts[1])
        
        self['user']['git_uri'] = git_uri
        
        res = ask_user('Default group [%s]: ' % user, can_be_empty=True)
        self['user']['default_group'] = res or user
        
        def_bp = user + '_personal'
        res = ask_user('Default build platform [%s]: ' % def_bp, can_be_empty=True)
        self['user']['default_build_platform'] = res or def_bp
        
        filestore_domain = self.ask_user_url('File-store URL [%s]: ' % Config.default_filestore_url, Config.default_filestore_url)
        self['main']['file_store_url'] = filestore_domain
        
        #configure logging       
        self['formatters']['keys'] = 'verbose,simple'
        self['formatter_verbose']['format'] = '%(asctime)s %(levelname)-7s in %(filename)s:%(funcName)s:%(lineno)d: %(message)s'
        self['formatter_simple']['format'] = '%(message)s'
        
        self['loggers']['keys'] = 'root,abf,beaker,models'
        self['logger_root']['handlers'] = 'verbose'
        self['logger_root']['propagate'] = '1'
        self['logger_root']['level'] = 'DEBUG'
        self['logger_root']['qualname'] = ''
        self['logger_abf']['handlers'] = 'main'
        self['logger_abf']['propagate'] = '0'
        self['logger_abf']['level'] = 'INFO'
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
        self['handler_main']['level'] = 'INFO'
        self['handler_main']['class'] = 'StreamHandler'
        self['handler_main']['formatter'] = 'simple'
        self['handler_main']['args'] = '()'
        
        self['main']['config_version'] = VERSION
        print('Initial configuration have been completed')
        print 'Now you can execute "abf locate update-recursive -d PATH", where PATH is your directory with ' + \
        'cloned ABF projects. It will let you use "abfcd <project>" command to simply cd to project directory.\n\n'

        
        
        

        