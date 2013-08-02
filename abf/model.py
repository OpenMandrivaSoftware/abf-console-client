# -*- coding: UTF-8 -*-
from beaker.cache import Cache
from beaker.util import parse_cache_config_options
import logging
import urllib2, urllib
import string
from datetime import datetime

from abf.api.exceptions import *
#from abf.api.html import *
from abf.api.jsn import *


log = logging.getLogger('models')

lt_cache = Cache('abf', expire = 86400, type='file', data_dir='/tmp/abf_cache/data', lock_dir='/tmp/abf_cache/data')
st_cache = Cache('abf', expire = 3600,  type='file', data_dir='/tmp/abf_cache/data', lock_dir='/tmp/abf_cache/data')
#lt_cache = None
#st_cache = None

def get_cached(cache, cache_key, func, *args, **kwargs):
    if cache and cache.has_key(cache_key):
        val = cache.get(cache_key)
    else:
        val = func(*args, **kwargs)
        if cache:
            cache.put(cache_key, val)
    return val


        
class Model(object):
    def __init__(self, models, ID=None, init_data=None):
        self.params_dict = {}
        self.ID = ID
        self.init_data = init_data
        self.models = models
        self.stub = True
        self.cacher = None

        if not ID and not init_data:
            raise Exception("At least one of 'ID' or 'init_data' parameters have to be set! ")
        
        if init_data and 'id' not in init_data:
            raise Exception("Key 'id' have to present in initial data!")
        
        if ID:
            cache_key = '%s-%s' % (self.__class__.__name__, ID)
            
            if st_cache and st_cache.has_key(cache_key):
                #read cached value
                log.debug( 'Loading %s %s from cache' % (self.__class__.__name__, ID))
                self.stub = False
                self.init_data = st_cache.get(cache_key)
                self.load()
                
            else:
                log.debug('Loading %s %s using API' % (self.__class__.__name__, ID))
                self.stub = False
                self.get_init_data(ID)
                self.load()
                
                #write to cache
                if self.cacher:
                    self.cacher.put(cache_key, self.init_data)
                    log.debug('Results were cached')
                    
            for field in self.__class__.required_fields:
                if field not in self.params_dict:
                    raise Exception("One of the fields required for %s model was not specified: %s" % 
                                (self.__class__.__name__, field))
        else:
            log.debug('Creating a stub for %s %s' % (self.__class__.__name__, self.init_data['id']))
            self.load()
            self.stub = True


    def __getattr__(self, key):
        if key == 'params_dict':
            return None
        if key in self.params_dict:
            return self.params_dict[key]
        if self.__dict__['stub']:
            #print 'REAL LOADING'
            self.stub = False
            obj = self.__class__(self.models, ID=self.params_dict['id'])
            self.__dict__ = obj.__dict__
            #self.load(self.params_dict['id'])
            if key in self.params_dict:
                return self.params_dict[key]
        raise KeyError("Key '%s' can not be found!" % key)
    
    def __eq__(self, other):
        return self.id == other.id
        
    def __ne__(self, other):
        return self.id != other.id   
        
        
class Platform(Model):
    required_fields = ['id', 'name', 'description', 'parent_platform_id', 'created_at', 'updated_at', 'released', 
    'owner', 'visibility', 'platform_type', 'distrib_type', 'repositories']

    def get_init_data(self, ID):
        ID = str(ID)
        log.debug('Reading platform ' + ID)
        self.init_data = self.models.jsn.get_platform_by_id(ID)
        self.init_data = self.init_data['platform']
            
    def load(self):        
        self.params_dict = self.init_data.copy()
        if 'repositories' in self.init_data:
            repos = self.params_dict['repositories']
            repositories = []
            for repo in repos:
                r = Repository(self.models, init_data=repo)
                r.params_dict['platform'] = self
                repositories.append(r)
            self.params_dict['repositories'] = repositories
        if 'owner' in self.init_data:
            self.params_dict['owner'] = User(self.models, init_data=self.init_data['owner'])
        if 'created_at' in self.init_data:
            self.params_dict['created_at'] = datetime.fromtimestamp(float(self.init_data['created_at']))
        if 'updated_at' in self.init_data:
            self.params_dict['updated_at'] = datetime.fromtimestamp(float(self.init_data['updated_at']))
        self.cacher = lt_cache
                 
    def __repr__(self):
        return self.name
        
    @staticmethod 
    def _get_platforms_filtered(models, typ):
        cache_key = '%s__%s' % (Platform.__name__, typ)
        platforms = get_cached(st_cache, cache_key, models.jsn.get_platforms, typ=typ)['platforms']
        output = []
        for pl in platforms:
            p = Platform(models, init_data = pl)
            output.append(p)
        return output
        
    @staticmethod
    def get_user_platforms_main(models):
        return Platform._get_platforms_filtered(models, 'main')
        
    @staticmethod
    def get_user_platforms_personal(models):
        return Platform._get_platforms_filtered(models, 'personal')
        
    @staticmethod
    def get_build_platforms(models):
        cache_key = '%s__buil' % (Platform.__name__)
        platforms = get_cached(st_cache, cache_key, models.jsn.get_build_platforms)['platforms']
        output = []
        for pl in platforms:
            p = Platform(models, init_data=pl)
            output.append(p)
        return output
        
    @staticmethod
    def search(models, query):
        res = models.jsn.get_search_results('platforms', query)
        platforms = res['results']['platforms']
        platforms_out = []
        for platform in platforms:
            p = Platform(models, init_data=platform)
            platforms_out.append(p)
        return platforms_out
        
        
class Repository(Model):
    required_fields = ['id', 'name', 'created_at', 'updated_at', 'description', 'publish_without_qa', 'platform']

    def get_init_data(self, ID):
        ID = str(ID)
        log.debug('Reading repository ' + str(ID))
        self.init_data = self.models.jsn.get_repository_by_id(ID)
        self.init_data = self.init_data['repository']
        
    def load(self):
        self.params_dict = self.init_data.copy()
        if 'platform' in self.init_data:
            self.params_dict['platform'] = Platform(self.models, init_data=self.params_dict['platform'])
        if 'created_at' in self.init_data:
            self.params_dict['created_at'] = datetime.fromtimestamp(float(self.init_data['created_at']))
        if 'updated_at' in self.init_data:
            self.params_dict['updated_at'] = datetime.fromtimestamp(float(self.init_data['updated_at']))
        self.cacher = lt_cache
            
        self.cacher = lt_cache
    
    def __repr__(self):
        return '%s/%s' % (self.platform.name, self.name)
        


class Arch(Model):
    required_fields = ['id', 'name']

    def get_init_data(self, ID):
        ID = str(ID)
        log.debug('Reading arch ' + str(ID))
        arches = self.models.jsn.get_architectures()['architectures']
        self.init_data = None
        for arch in arches:
            if str(arch['id']) == ID:
                self.init_data = arch
        if not self.init_data:
            raise Exception("Architecture with id %s not found!" % ID)
                
    def load(self):
        self.params_dict = self.init_data
        self.cacher = lt_cache
    
    @staticmethod
    def get_arches(models):
        cache_key = '%s__all' % (Arch.__name__)
        arches = get_cached(st_cache, cache_key, models.jsn.get_architectures)['architectures']
        output = []
        for arch in arches:
            a = Arch(models, init_data=arch)
            output.append(a)
        return output
        
    @staticmethod
    def get_arch_by_name(models, name):
        cache_key = '%s__all' % (Arch.__name__)
        arches = get_cached(st_cache, cache_key, models.jsn.get_architectures)['architectures']
        for arch in arches:
            if arch['name'] == name:
                a = Arch(models, init_data=arch)
                return a
        return None
        
    def __repr__(self):
        return self.name
        
class User(Model):
    required_fields = ['id', 'name', 'email', 'language', 'professional_experience', 'site', 'company', 'location',
    'uname', 'own_projects_count', 'build_priority', 'created_at', 'updated_at', 'avatar_url', 'html_url']

    def get_init_data(self, ID):
        ID = str(ID)
        log.debug('Reading user ' + ID)
        self.init_data = self.models.jsn.get_user_by_id(ID)
        self.init_data = self.init_data['user']
            
    def load(self):        
        self.params_dict = self.init_data.copy()
        
        if 'created_at' in self.init_data:
            self.params_dict['created_at'] = datetime.fromtimestamp(float(self.init_data['created_at']))
        if 'updated_at' in self.init_data:
            self.params_dict['updated_at'] = datetime.fromtimestamp(float(self.init_data['updated_at']))
        
        self.cacher = lt_cache
    
    @staticmethod
    def search(models, query):
        res = models.jsn.get_search_results('users', query)
        users = res['results']['users']
        users_out = []
        for user in users:
            u = User(models, init_data=user)
            users_out.append(u)
        return users_out
    
    def __repr__(self):
        return self.uname
        
class Group(Model):
    required_fields = ['id', 'uname', 'own_projects_count', 'created_at', 'updated_at', 'description', 'owner',
                                                                                'avatar_url', 'html_url']

    def get_init_data(self, ID):
        ID = str(ID)
        log.debug('Reading group ' + ID)
        self.init_data = self.models.jsn.get_group_by_id(ID)
        self.init_data = self.init_data['group']
            
    def load(self):        
        self.params_dict = self.init_data.copy()
        
        if 'created_at' in self.init_data:
            self.params_dict['created_at'] = datetime.fromtimestamp(float(self.init_data['created_at']))
        if 'updated_at' in self.init_data:
            self.params_dict['updated_at'] = datetime.fromtimestamp(float(self.init_data['updated_at']))
        
        if 'owner' in self.params_dict:
            self.params_dict['owner'] = User(self.models, init_data=self.params_dict['owner'])
        
        self.cacher = lt_cache
        
    @staticmethod
    def search(models, query):
        res = models.jsn.get_search_results('groups', query)
        groups = res['results']['groups']
        groups_out = []
        for group in groups:
            g = Group(models, init_data=group)
            groups_out.append(g)
        return groups_out
    
        
    def __repr__(self):
        return self.uname
        
class Project(Model):
    required_fields = ['id', 'name', 'created_at', 'updated_at', 'visibility', 'description', 'ancestry', 'has_issues', 
            'has_wiki', 'default_branch', 'is_package', 'owner', 'repositories', 'owner_type']
#            'has_wiki', 'default_branch', 'is_package', 'average_build_time', 'owner', 'repositories', 'owner_type']

    def get_init_data(self, proj_id):
        log.debug("Reading project " + str(proj_id))
        self.init_data = self.models.jsn.get_project_by_id(proj_id)
        self.init_data = self.init_data['project']
    
    @staticmethod
    def get_by_name(models, key):
        ''' key is a pair (owner_name, project_name), or just  owner_name/project_name'''
        if type(key) is unicode or type(key) is str:
            items = key.split('/')
            if len(items) != 2:
                raise Exception('Invalid key: ' + key)
            key = (items[0], items[1])
        res = models.jsn.get_project_id_by_name(key)
        proj_id = res['project']['id']
        return Project(models, ID=proj_id)
        
    def load(self):
        self.params_dict = self.init_data.copy()
        if 'repositories' in self.init_data:
            repos = self.params_dict['repositories']
            self.params_dict['repositories'] = []
            for repo in repos:
                r = Repository(self.models, init_data=repo)
                self.params_dict['repositories'].append(r)
        if 'owner' in self.init_data:
            self.params_dict['owner_type'] = self.init_data['owner']['type']
            if self.params_dict['owner_type'] == 'User':
                self.params_dict['owner'] = User(self.models, init_data=self.init_data['owner'])
            elif self.params_dict['owner_type'] == 'Group':
                self.params_dict['owner'] = Group(self.models, init_data=self.init_data['owner'])
            
        if 'created_at' in self.init_data:
            self.params_dict['created_at'] = datetime.fromtimestamp(float(self.init_data['created_at']))
        if 'updated_at' in self.init_data:
            self.params_dict['updated_at'] = datetime.fromtimestamp(float(self.init_data['updated_at']))
            
        self.cacher = st_cache
        
    @staticmethod
    def search(models, query):
        res = models.jsn.get_search_results('projects', query)
        projs = res['results']['projects']
        projects_out = []
        for proj in projs:
            pr = Project(models, init_data=proj)
            projects_out.append(pr)
        return projects_out
                
    def __repr__(self):
        if 'owner' in self.params_dict:
            return '%s/%s' % (self.owner.uname, self.name) 
        else:
            return self.fullname
        
    def get_refs_list(self, models):
        return self.models.jsn.get_git_refs_list(self.id)['refs_list']
        
        
class BuildList(Model):
    required_fields = ['id', 'container_path', 'status', 'status_string', 'package_version', 'project', 'created_at', 'updated_at',
    'build_for_platform', 'save_to_repository', 'arch', 'update_type', 'auto_publish', 'extra_repositories',
    'commit_hash', 'duration', 'owner', 'owner_type', 'include_repos', 'priority', 'build_log_url', 'advisory', 'mass_build']
    
    status_by_id = {
        0: 'build complete',
        1: 'platform not found',
        2: 'platform pending',
        3: 'project not found',
        4: 'project version not found',
        666: 'build error',
        2000: 'build pending',
        3000: 'build started',
        4000: 'waiting for response',
        5000: 'build canceled',
        6000: 'build has been published',
        7000: 'build is being published',
        8000: 'publishing error',
        9000: 'publishing rejected',
        10000: 'build is canceling',
        11000: 'tests failed',
    }
    status_by_name = dict([(status_by_id[x], x) for x in status_by_id])
    final_statuses = [1, 2, 3, 4, 666, 5000, 6000, 8000, 9000]
        
    def get_init_data(self, ID):
        ID = str(ID)
        log.debug('Reading buildlist ' + str(ID))
        self.init_data = self.models.jsn.get_buildlist_by_id(ID)
        self.init_data = self.init_data['build_list']
        
        
    def load(self):  
        self.params_dict = self.init_data.copy()

        self.params_dict['project'] = Project(self.models, init_data=self.params_dict['project'])
        self.params_dict['arch'] = Arch(self.models, init_data=self.params_dict['arch'])
        self.params_dict['save_to_repository'] = Repository(self.models, init_data=self.params_dict['save_to_repository'])
        self.params_dict['build_for_platform'] = Platform(self.models, init_data=self.params_dict['build_for_platform'])
        

        include_repos = self.params_dict['include_repos']
        self.params_dict['include_repos'] = []
        for rep in include_repos:
            r = Repository(self.models, init_data=rep)
            self.params_dict['include_repos'].append(r)

        extra_repositories = self.params_dict['extra_repositories']
        self.params_dict['extra_repositories'] = []
        for rep in extra_repositories:
            r = Repository(self.models, init_data=rep)
            self.params_dict['extra_repositories'].append(r)
        
        self.params_dict['owner_type'] = self.init_data['owner']['type']
        if self.params_dict['owner_type'] == 'User':
            self.params_dict['owner'] = User(self.models, init_data=self.init_data['owner'])
        elif self.params_dict['owner_type'] == 'Group':
            self.params_dict['owner'] = Group(self.models, init_data=self.init_data['owner'])
                
        #self.params_dict['owner'] = User(self.models, init_data=self.init_data['owner'])
        if 'created_at' in self.init_data:
            self.params_dict['created_at'] = datetime.fromtimestamp(float(self.init_data['created_at']))
        if 'updated_at' in self.init_data:
            self.params_dict['updated_at'] = datetime.fromtimestamp(float(self.init_data['updated_at']))

        
        self.params_dict['status_string'] = BuildList.status_by_id[self.params_dict['status']]
        if self.params_dict['status'] in BuildList.final_statuses:
            self.cacher = lt_cache        
        
        
    def __repr__(self):
        return '%s (%s/%s:%s - %s)' % (self.id, self.owner.uname, self.project.name, 
                self.arch.name, self.status_string)
                
    update_types = ['security', 'bugfix', 'enhancement', 'recommended', 'newpackage']
    @staticmethod
    def new_build_task(models, project, save_to_repository, repositories, commit_hash, update_type, auto_publish, arches, skip_personal):
        DATA = {
            'project_id': project.id,
            'commit_hash': commit_hash,
            'update_type': update_type, 
            'save_to_repository_id': save_to_repository.id,
            'build_for_platform_id': None,
            'auto_publish': auto_publish,
            'auto_create_container': True,
            'arch_id': None,
            'include_repos': [],
            'extra_repositories': [],
            }
        build_platforms = {}

        if not skip_personal and string.find(save_to_repository.platform.name,"_personal") > 0:
            DATA['extra_repositories'].append(save_to_repository.id)

        for repo in repositories:
            if repo.platform.name not in build_platforms:
                build_platforms[repo.platform.name] = {}
                build_platforms[repo.platform.name]['repositories'] = []
                build_platforms[repo.platform.name]['id'] = repo.platform.id
            build_platforms[repo.platform.name]['repositories'].append(repo.id)
        build_ids = []    
        for bpl in build_platforms:
            DATA['build_for_platform_id'] = build_platforms[bpl]['id']
            DATA['include_repos'] = build_platforms[bpl]['repositories']

            for arch in arches:
                DATA['arch_id'] = arch.id
                log.debug('Sending the build task: ' + str(DATA))
                try:
                    #continue
                    result = models.jsn.new_build_task({'build_list': DATA})
                except BadRequestError, ex:
                    log.error('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                        'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s' % DATA )
                    exit(1)
                log.info("Task %s|%s|%s|%s have been sent. Build task id is %s" % 
                    (project, bpl, save_to_repository, arch, result['build_list']['id']))
                build_ids.append(result['build_list']['id'])
        return build_ids
                    
    def publish(self):
        try:
            log.info("Publishing the project %s..." % self.id)
            result = self.models.jsn.publish(self.id)
            if result['is_published']:
                log.info(result['message'])
            else:
                log.error(result['message'])
               
            return result
        except BadRequestError, ex:
            log.error('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s' % DATA )
            exit(1)
        
    
class Models(object):
    _instance = {}
    def __new__(cls, abf_url, file_store_url, login, password, *args, **kwargs):
        tmp = '%s:%s:%s:%s' % (abf_url, file_store_url, login, password)
        if tmp not in cls._instance:
            cls._instance[tmp] = super(Models, cls).__new__(
                                cls, abf_url, file_store_url, login, password, *args, **kwargs)
        return cls._instance[tmp]
        
    #properties_by_class = {Platform: 'platforms', Repository: 'repositories', Arch: 'arches',
    #        BuildList: 'buildlists', Project: 'projects'}
    #properties_by_name = dict([(properties_by_class[x], x) for x in properties_by_class])
        
    def __init__(self, abf_url, file_store_url, login, password):
        log.debug('Initializing models for ' + abf_url)
        self.abf_url = abf_url
        self.file_store_url = file_store_url
        self.login = login
        self.password = password
        self.jsn = AbfJson(abf_url, file_store_url, login, password, log)
    
        
    @staticmethod
    def clear_cache():
        lt_cache.clear()
        st_cache.clear()


        