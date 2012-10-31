import urllib2, urllib
import re
import json
import os
import base64
import pdb


from abf.api.exceptions import *


from beaker.cache import Cache
from beaker.util import parse_cache_config_options
cache_data = Cache('abf_etag_data', expire = 86400, type='file', data_dir='/tmp/abf_cache/etag_data', lock_dir='/tmp/abf_cache/etag_data')
cache_etags = Cache('abf_etags', expire = 86400, type='file', data_dir='/tmp/abf_cache/etags', lock_dir='/tmp/abf_cache/etags')


class AbfJson(object):
    def __init__(self,abf_url, login, password, log):
        self.login = login
        self.password = password
        self.abf_url = re.compile('/+$').sub('',abf_url)
        
        #does not work sometimes
        '''self.password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_manager.add_password(None, abf_url, login, password)
        self.auth = urllib2.HTTPBasicAuthHandler(self.password_manager) 
        self.opener = urllib2.build_opener(self.auth)
        urllib2.install_opener(self.opener)
        '''
        
        # but it works!
        self.base64_auth_string = base64.standard_b64encode('%s:%s' % (login, password)).replace('\n', '')
        self.log = log

    errors = {
        "Invalid email or password.": AuthError,
        "403 Forbidden | Rate Limit Exceeded": RateLimitError,
        "Page not found": PageNotFoundError,
        "Error 404. Resource not found!": PageNotFoundError,
        "Something went wrong. We've been notified about this issue and we'll take a look at it shortly.": InternalServerError,
        "We update the site, it will take some time. We are really trying to do it fast. We apologize for any inconvenience..": ServerWorksError,
        "Requires authentication": AuthError,
        "Forbidden. Sorry, you don't have enough rights for this action!": ForbiddenError,
        "Access violation to this page!": ForbiddenError,
        "Bad Request": BadRequestError,}
    good_messages = ['Errors during build publishing!', 'Build is queued for publishing']
        
    # in case of this error, get_url_contents will print the error message and exit
    fatal_errors = [AuthError, RateLimitError, InternalServerError, ServerWorksError]
        
    def get_url_contents(self, url, GET=None, POST=None):
        url = self.abf_url + url
        if GET:
            get_string = urllib.urlencode(GET)
            if '?' in url:
                url = url + '&' + get_string
            else:
                url = url + '?' + get_string
        self.log.debug('Fetching url %s' % url)

        etag = None
        if POST:
            post_json = json.dumps(POST).encode('utf-8')
            request = urllib2.Request(url, post_json, {'Content-Type': 'application/json'})
        else:
            request = urllib2.Request(url)
            
            if cache_etags.has_key(url) :
                etag = cache_etags.get(url)
                self.log.debug("It was cached! ETag: " + etag)
                request.add_header("If-None-Match", etag) 
                
        
        request.add_header("Authorization", "Basic %s" % self.base64_auth_string)  
        etag_new = None
        try:
            result = urllib2.urlopen(request)
            res = result.read()
            etag_new = result.headers.getheaders('ETag')[0]
        except urllib2.HTTPError, ex:
            if ex.code == 304: # data was not modified
                res = cache_data.get(etag)
                self.log.debug('Getting cached result (cache was validated)')
            else:
                self.log.debug('Return code: ' + str(ex.code))

                if ex.code == 401: # auth failed
                    self.log.error("Authorization failed. Incorrect username or password")
                    exit()
                    
                #remove cached data if exists
                if etag:
                    try:
                        cache_etags.remove(url)
                        cache_data.remove(etag)
                    except:
                        pass
                res = ex.fp.read()
                
        if etag_new:
            self.log.debug("Caching the new value for %s. ETag is %s" % (url, etag_new))
            cache_etags.put(url, etag_new)
            cache_data.put(etag_new, res)
            
        try:
            res = json.loads(res)
        except ValueError, ex:
            self.log.error("Internal server error: it have returned non-json data. ")
            exit(1)
        
        if 'message' in res and res['message'] not in AbfJson.good_messages:
            m = res['message']
            if m in AbfJson.errors:
                self.log.debug(m)
                exception = AbfJson.errors[m]
            else:
                self.log.error("Unknown server error: " + m)
                exception = AbfApiException
            if exception == BadRequestError:
                log.error('Sorry, but something went wrong and request I\'ve sent to ABF is bad. Please, '
                    'notify developers, send them a set of command-line arguments and the request data:\n%s\n%s' % (URL, post_json or "No POST DATA") )
                exit(1)
                
            if exception in AbfJson.fatal_errors:
                exit(2)
            raise exception(m)
  
        #print 'RAW OUTPUT', res
        return res
        
    def get_architectures(self):
        URL = "/api/v1/arches.json"
        return self.get_url_contents(URL)
    
    def get_platforms(self, typ=None):
        URL = "/api/v1/platforms.json"
        GET = {}
        if typ:
            GET['type'] = typ
        return self.get_url_contents(URL, GET)
        
    def get_platform_by_id(self, pl_id):
        pl_id = int(pl_id)
        URL = "/api/v1/platforms/%d.json" % pl_id
        return self.get_url_contents(URL)
        
    def get_build_platforms(self):
        URL = "/api/v1/platforms/platforms_for_build.json" 
        return self.get_url_contents(URL)
        
    def get_repository_by_id(self, rep_id):
        rep_id = int(rep_id)
        URL = "/api/v1/repositories/%d.json" % rep_id
        return self.get_url_contents(URL)
        
    def get_buildlist_by_id(self, bl_id):
        bl_id = int(bl_id)
        URL = "/api/v1/build_lists/%d.json" % bl_id
        return self.get_url_contents(URL)
        
    def get_project_by_id(self, p_id):
        p_id = int(p_id)
        URL = "/api/v1/projects/%d.json" % p_id
        return self.get_url_contents(URL)
        
    def get_project_id_by_name(self, key):
        proj_owner, proj_name = key
        URL = "/api/v1/projects/get_id.json"
        GET = {'name': proj_name, 'owner':proj_owner}
        return self.get_url_contents(URL, GET)
        
    def new_build_task(self, data):
        URL = "/api/v1/build_lists.json"
        return self.get_url_contents(URL, GET=None, POST=data)
        
    def publish(self, task_id):
        task_id = int(task_id)
        URL = "/api/v1/build_lists/%d/publish.json" % task_id
        return self.get_url_contents(URL)
        
    def get_git_refs_list(self, proj_id):
        proj_id = int(proj_id)
        URL = "/api/v1/projects/%d/refs_list.json"  % proj_id
        return self.get_url_contents(URL)
        
    def get_user_by_id(self, user_id):
        user_id = int(user_id)
        URL = "/api/v1/users/%d.json" % user_id
        return self.get_url_contents(URL)
        
    def get_group_by_id(self, group_id):
        group_id = int(group_id)
        URL = "/api/v1/groups/%d.json" % group_id
        return self.get_url_contents(URL)
        
        