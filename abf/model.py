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
            raise Exception(_("At least one of 'ID' or 'init_data' parameters have to be set! "))

        if init_data and 'id' not in init_data:
            raise Exception(_("Key 'id' have to present in initial data!"))

        if ID:
            cache_key = '%s-%s' % (self.__class__.__name__, ID)

            if st_cache and st_cache.has_key(cache_key):
                #read cached value
                log.debug( _('Loading %(name)s %(id)s from cache') % {'name': self.__class__.__name__, 'id': ID})
                self.stub = False
                self.init_data = st_cache.get(cache_key)
                self.load()

            else:
                log.debug(_('Loading %(name)s %(id)s using API') % {'name': self.__class__.__name__, 'id': ID})
                self.stub = False
                self.get_init_data(ID)
                self.load()

                #write to cache
                if self.cacher:
                    self.cacher.put(cache_key, self.init_data)
                    log.debug(_('Results were cached'))

            for field in self.__class__.required_fields:
                if field not in self.params_dict:
                    raise Exception(_("One of the fields required for %(name)s model was not specified: %(field)s") %
                                {'name': self.__class__.__name__, 'field': field})
        else:
            log.debug(_('Creating a stub for %(name)s %(id)s') % {'name': self.__class__.__name__, 'id': self.init_data['id']})
            self.load()
            self.stub = True


    def __getattr__(self, key):
        if key == 'params_dict':
            return None
        if key in self.params_dict:
            return self.params_dict[key]
        if self.__dict__['stub']:
            self.stub = False
            obj = self.__class__(self.models, ID=self.params_dict['id'])
            self.__dict__ = obj.__dict__
            #self.load(self.params_dict['id'])
            if key in self.params_dict:
                return self.params_dict[key]
        raise KeyError(_("Key '%s' can not be found!") % key)

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id


class Platform(Model):
    required_fields = ['id', 'name', 'description', 'parent_platform_id', 'created_at', 'updated_at', 'released',
    'owner', 'visibility', 'platform_type', 'distrib_type', 'repositories']
    filter_dict = { 'id': '*', 'name': '*', 'visibility': '*', 'owner': '*', 'platform_type': '*', 'repositories': '*', 'page': '1' }

    def get_init_data(self, ID):
        ID = str(ID)
        log.debug(_('Reading platform ') + ID)
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

    @staticmethod
    def info(models):
        if Platform.filter_dict['page'] == '*':
            num = 1
            while 1:
                res = models.jsn.get_list('platforms', num)
                if not res['platforms']:
                    break
                platforms += res['platforms']
                num += 1
        else:
            res = models.jsn.get_list('platforms', Platform.filter_dict['page'])
            platforms = res['platforms']
        platforms = res['platforms']
        platforms_out = []
        for platform in platforms:
            p = Platform(models, init_data=platform)
            platforms_out.append(p)
            for value in Platform.filter_dict:
                if Platform.filter_dict[value] != '*' and value != 'page':
                    platforms_out = [i for i in platforms_out if str(Platform.filter_dict[value]) in str(i.params_dict[value]) ]
        return platforms_out

class Repository(Model):
    required_fields = ['id', 'name', 'created_at', 'updated_at', 'description', 'publish_without_qa', 'platform']
    filter_dict = { 'id': '*', 'name': '*', 'page': '1' }

    def get_init_data(self, ID):
        ID = str(ID)
        log.debug(_('Reading repository ') + str(ID))
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

    def __repr__(self):
        return '%s/%s' % (self.platform.name, self.name)

    @staticmethod
    def info(models):
        platform_info = Platform.info(models)
        repo_info = []
        for platform in platform_info:
            repos = platform.params_dict['repositories']
            for repo in repos:
                repo_fin = Repository(models, repo.id)
                repo_info.append(repo_fin)
            for value in Repository.filter_dict:
                if Repository.filter_dict[value] != '*' and value != 'page':
                    repo_info = [i for i in repo_info if str(Repository.filter_dict[value]) in str(i.params_dict[value]) ]
        return repo_info


class Arch(Model):
    required_fields = ['id', 'name']

    def get_init_data(self, ID):
        ID = str(ID)
        log.debug(_('Reading arch ') + str(ID))
        arches = self.models.jsn.get_architectures()['architectures']
        self.init_data = None
        for arch in arches:
            if str(arch['id']) == ID:
                self.init_data = arch
        if not self.init_data:
            raise Exception(_("Architecture with id %s not found!") % ID)

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
        log.debug(_('Reading user ') + ID)
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
        log.debug(_('Reading group ') + ID)
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
    required_fields = ['id', 'name', 'fullname', 'git_url', 'created_at', 'updated_at', 'visibility', 'description', 'ancestry', 'has_issues',
            'has_wiki', 'default_branch', 'is_package', 'owner', 'repositories', 'owner_type', 'maintainer', 'project_statistics',]
    filter_dict = { 'id': '*', 'name': '*', 'page': '1' }


    def get_init_data(self, proj_id):
        log.debug(_("Reading project ") + str(proj_id))
        self.init_data = self.models.jsn.get_project_by_id(proj_id)
        self.init_data = self.init_data['project']

    @staticmethod
    def get_by_name(models, key):
        ''' key is a pair (owner_name, project_name), or just  owner_name/project_name'''
        if type(key) is unicode or type(key) is str:
            items = key.split('/')
            if len(items) != 2:
                raise Exception(_('Invalid key: ') + key)
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
        if 'ancestry' in self.init_data:
            ancestry = self.params_dict['ancestry']
            if ancestry:
                self.params_dict['ancestry'] = []
                items = ancestry.split('/')
                for item in items:
                    anc_proj=self.models.jsn.get_project_by_id(item)
                    self.params_dict['ancestry'].append(anc_proj['project']['fullname'])
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

    @staticmethod
    def info(models):
        repo_info = Repository.info(models)
        projects_info = []
        projs = []
        for repo in repo_info:
            if Project.filter_dict['page'] == '*':
                num = 1
                while 1:
                    p = models.jsn.get_projects_single(repo.id, num)
                    if not p['repository']['projects']:
                        break
                    projs += p['repository']['projects']
                    num += 1
            else:
                p = models.jsn.get_projects_single(repo.id, Project.filter_dict['page'])
                projs = p['repository']['projects']
            for proj in projs:
                pr = Project(models, init_data=proj)
                projects_info.append(pr)
        for value in Project.filter_dict:
            if Project.filter_dict[value] != '*' and value != 'page':
                projects_info = [i for i in projects_info if str(Project.filter_dict[value]) in str(i.params_dict[value]) ]
        return projects_info

    @staticmethod
    def update(models, project, name, description, visibility, is_package, default_branch,
		has_issues, has_wiki, publish_i686_into_x86_64, maintainer_id):
        DATA = {
            'id': project.id,
            'name': name,
            'description': description,
            'visibility': visibility,
            'is_package': is_package,
            'default_branch': default_branch,
            'has_issues': has_issues,
            'has_wiki': has_wiki,
            'publish_i686_into_x86_64': publish_i686_into_x86_64,
            'maintainer_id': maintainer_id,
            }

        log.debug(_('Updating project settings: ') + str(DATA))
        try:
            result = models.jsn.update_project({'project': DATA}, project.id)
        except BadRequestError, ex:
            log.error(_('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s') % DATA )
            exit(1)
        log.info(_("Successfully updated settings of project %s.") % (project.name))

class BuildList(Model):
    required_fields = ['id', 'container_path', 'status', 'status_string', 'package_version', 'project', 'created_at', 'updated_at',
    'build_for_platform', 'save_to_repository', 'arch', 'update_type', 'extra_repositories',
    'commit_hash', 'duration', 'include_repos', 'priority', 'build_log_url', 'advisory', 'mass_build', 'log_url', 'chroot_tree']

    status_by_id = {
        0: 'build complete',
        1: 'platform not found',
        2: 'platform pending',
        3: 'project not found',
        4: 'project version not found',
        6: 'project source error',
        555: 'dependencies error',
        666: 'build error',
        777: 'packages fail',
        2000: 'build pending',
        2500: 'rerun tests',
        2550: 'rerunning tests',
        3000: 'build started',
        4000: 'waiting for response',
        5000: 'build canceled',
        6000: 'build has been published',
        7000: 'build is being published',
        8000: 'publishing error',
        9000: 'publishing rejected',
        10000: 'build is canceling',
        11000: 'tests failed',
        12000: '[testing] Build has been published',
        13000: '[testing] Build is being published',
        14000: '[testing] Publishing error',
        15000: 'unpermitted architecture'
    }
    status_by_name = dict([(status_by_id[x], x) for x in status_by_id])
    final_statuses = [1, 2, 3, 4, 666, 5000, 6000, 8000, 9000, 12000, 14000]

    container_status_by_id = {
        4000: 'waiting for request for publishing container',
        6000: 'container has been published',
        7000: 'container is being published',
        8000: 'publishing error'
    }
    container_status_by_name = dict([(container_status_by_id[x], x) for x in container_status_by_id])

    def get_init_data(self, ID):
        ID = str(ID)
        log.debug(_('Reading buildlist ') + str(ID))
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


        self.params_dict['owner_type'] = 'Group'
        if 'created_at' in self.init_data:
            self.params_dict['created_at'] = datetime.fromtimestamp(float(self.init_data['created_at']))
        if 'updated_at' in self.init_data:
            self.params_dict['updated_at'] = datetime.fromtimestamp(float(self.init_data['updated_at']))


        self.params_dict['chroot_tree'] = ''
        if self.init_data['logs']:
    	    self.params_dict['log_url'] = self.init_data['logs'][0]['url'] + '.log?show=True'
    	    for log in self.init_data['logs']:
    	        if log["file_name"] == "chroot-tree.log":
    	            self.params_dict["chroot_tree"] = log["url"] + '.log?show=True'
        else:
    	    self.params_dict['log_url'] = ''

        self.params_dict['status_string'] = BuildList.status_by_id[self.params_dict['status']]
        if self.params_dict['status'] in BuildList.final_statuses:
            self.cacher = lt_cache

        self.params_dict['container_status_string'] = BuildList.container_status_by_id[self.params_dict['container_status']]


    def __repr__(self):
        return '%s (%s:%s - %s)' % (self.id, self.project.fullname,
                self.arch.name, self.status_string)

    update_types = ['security', 'bugfix', 'enhancement', 'recommended', 'newpackage']
    auto_publish_statuses = ['default', 'none', 'testing']
    @staticmethod
    def new_build_task(models,
			project,
			save_to_repository,
			repositories,
			commit_hash,
			project_version,
			update_type,
			auto_publish_status,
			arches, skip_personal,
			cached_chroot,
			save_chroot,
			auto_create_container,
			include_testing_subrepo,
			use_extra_tests,
			extra_build_lists):
        DATA = {
            'project_id':               project.id,
            'commit_hash':              commit_hash,
            'update_type':              update_type,
            'save_to_repository_id':    save_to_repository.id,
            'build_for_platform_id':    None,
            'auto_publish_status':      auto_publish_status,
            'project_version':          project_version,
            'auto_create_container':    auto_create_container,
            'use_cached_chroot':	cached_chroot,
            'save_buildroot':		save_chroot,
            'arch_id':                  None,
            'include_repos':            [],
            'extra_repositories':       [],
            'extra_build_lists':        extra_build_lists,
            'include_testing_subrepository': include_testing_subrepo,
            'use_extra_tests':		use_extra_tests
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
                log.debug(_('Sending the build task: ') + str(DATA))
                try:
                    result = models.jsn.new_build_task({'build_list': DATA})
                except BadRequestError, ex:
                    log.error(_('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                        'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s') % DATA )
                    exit(1)
                log.info(_("Task %(proj)s|%(plat)s|%(save_repo)s|%(arch)s has been sent. Build task id is %(id)s") %
                    {'proj': project, 'plat': bpl, 'save_repo': save_to_repository, 'arch': arch, 'id': result['build_list']['id']})
                build_ids.append(result['build_list']['id'])
        return build_ids

    def publish(self):
        try:
            log.info(_("Publishing the project %s...") % self.id)
            result = self.models.jsn.publish(self.id)
            if result['is_published']:
                log.info(result['message'])
            else:
                log.error(result['message'])

            return result
        except BadRequestError, ex:
            log.error(_('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s') % DATA )
            exit(1)


class PullRequest(Model):
    required_fields = ['title', 'body', 'to_ref', 'from_ref']

    def load(self):
        self.params_dict = self.init_data.copy()
        self.params_dict['project'] = Project(self.models, init_data=self.params_dict['project'])

    def __repr__(self):
        return '%s: %s - %s' % (self.title, self.to_ref,
                self.from_ref)

    @staticmethod
    def new_pull_request(models, project, dest_project, title, body, to_ref, from_ref):
        DATA = {
            'from_project_id': project.id,
            'title': title,
            'body': body,
            'to_ref': to_ref,
            'from_ref': from_ref,
            }

        log.debug(_('Sending pull request: ') + str(DATA))
        try:
            #continue
            result = models.jsn.new_pull_request({'pull_request': DATA}, dest_project.id)
        except BadRequestError, ex:
            log.error(_('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s') % DATA )
            exit(1)
        log.info(_("Pull request from %(proj)s/%(from)s to %(dest_proj)s/%(to)s has been sent.") % {'proj': project, 'from': from_ref, 'to': to_ref, 'dest_proj': dest_project})

class ProjectCreator(Model):
    required_fields = ['name', 'description', 'owner']

    def load(self):
        self.params_dict = self.init_data.copy()
        self.params_dict['project'] = Project(self.models, init_data=self.params_dict['project'])

    def __repr__(self):
        return '%s (%s)' % (self.name, self.owner)

    @staticmethod
    def new_project(models, name, description, owner_id, owner_type):
        DATA = {
            'name': name,
            'owner_id': owner_id,
            'owner_type': owner_type,
            'visibility': 'open',
            'description': description,
            'is_package': 'true',
            'default_branch': 'master',
            'has_issues': 'true',
            'has_wiki': 'false',
            }

        log.debug(_('Creating project: ') + str(DATA))
        try:
            result = models.jsn.new_project({'project': DATA})
        except BadRequestError, ex:
            log.error(_('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s') % DATA )
            exit(1)
        log.info(_("The project %(name)s for owner %(owner)d has been created.") % {'name': name, 'owner': owner_id})

    @staticmethod
    def add_project_to_repo(models, repo_id, project_id):
        DATA = {
            'project_id': project_id,
            }

        log.debug(_('Adding project to repository: ') + str(DATA))
        try:
            result = models.jsn.add_project_to_repo(DATA, repo_id)
        except BadRequestError, ex:
            log.error(_('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s') % DATA )
            exit(1)
        log.info(_("The project %(project)d has been added to repository %(repo)d.") % {'project': project_id, 'repo': repo_id} )
        # Would be nice to invalidate only record corresponding to our project...
        models.clear_cache()

    @staticmethod
    def remove_project_from_repo(models, repo_id, project_id):
        DATA = {
            'project_id': project_id,
            }

        log.debug(_('Removing project from repository: ') + str(DATA))
        try:
            result = models.jsn.remove_project_from_repo(DATA, repo_id)
        except BadRequestError, ex:
            log.error(_('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s') % DATA )
            exit(1)
        log.info(_("The project has been removed from repository."))
        # Would be nice to invalidate only record corresponding to our project...
        models.clear_cache()

    @staticmethod
    def fork_project(models, proj_id, owner_id, target_name):
        if owner_id > 0:
            DATA = {
                'fork_name': target_name,
                'group_id': owner_id,
                }
        else:
            DATA = {
                'fork_name': target_name,
                }

        log.debug(_('Forking project: ') + str(DATA))
        try:
            result = models.jsn.fork_project(DATA, proj_id)
        except BadRequestError, ex:
            log.error(_('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s') % DATA )
            exit(1)
        log.info(_("The project has been forked."))

    @staticmethod
    def alias_project(models, proj_id, owner_id, target_name):
        if owner_id > 0:
            DATA = {
                'fork_name': target_name,
                'group_id': owner_id,
                }
        else:
            DATA = {
                'fork_name': target_name,
                }

        log.debug(_('Creating alias for a project: ') + str(DATA))
        try:
            result = models.jsn.alias_project(DATA, proj_id)
        except BadRequestError, ex:
            log.error(_('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s') % DATA )
            exit(1)
        log.info(_("The project alias has been created."))

    @staticmethod
    def destroy_project(models, proj_id):
        DATA = {
            'id': proj_id,
            }
        log.debug(_('Destroying project: ') + str(proj_id))
        try:
            result = models.jsn.destroy_project(DATA, proj_id)
        except BadRequestError, ex:
            log.error(_('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                'notify the console-client developers. Send them a set of command-line arguments and the request data:\n%s') % DATA )
            exit(1)
        log.info(_("The project has been destroyed."))


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
        log.debug(_('Initializing models for ') + abf_url)
        self.abf_url = abf_url
        self.file_store_url = file_store_url
        self.login = login
        self.password = password
        self.jsn = AbfJson(abf_url, file_store_url, login, password, log)


    @staticmethod
    def clear_cache():
        lt_cache.clear()
        st_cache.clear()



