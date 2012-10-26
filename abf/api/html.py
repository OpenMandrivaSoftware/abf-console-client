from BeautifulSoup import BeautifulSoup
import cookielib
from datetime import datetime
import mechanize
import re


class AbfHtml(object):
    # Mechanize "Browser" object.  Contains state about login information.
    br = None

    def __init__(self,abf_url,login,password):
        self.abf_url = re.compile('/+$').sub('',abf_url)

        # Log in to ABF
        # FIXME: there's no way to understand if the login/password were not OK for now

        # Browser
        br = mechanize.Browser()
        # Cookie Jar
        cj = cookielib.LWPCookieJar()
        br.set_cookiejar(cj)
        # Browser options
        br.set_handle_equiv(True)
        br.set_handle_gzip(True)
        br.set_handle_redirect(True)
        br.set_handle_referer(True)
        br.set_handle_robots(False)
        # Follows refresh 0 but not hangs on refresh > 0
        br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)
        # User-Agent (this is cheating, ok?)
        br.addheaders = [('User-agent', 'FBA Backend (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
        # The site we will navigate into, handling it's session
        self.opener = mechanize.build_opener()
        br.open('%s/users/sign_in' % self.abf_url)
        # Select the first (index zero) form
        br.select_form(nr=0)
        # User credentials
        br.form['user[login]'] = login
        br.form['user[password]'] = password
        br.form.find_control('user[remember_me]','checkbox').value = ['1']
        # Login
        br.submit()

        self.br = br

    def get_page_parser(self, uri):
        ''' Get the actual HTML and prepare the parser '''
        self.br.open(uri)
        return BeautifulSoup(self.br.response().read())
        
    # NOTE!  Build list id is a STRING rather than an INTEGER!
    def latest_build_lists(self, platform_id, page_n = 1):
        # Open the page
        uri = '%s/build_lists?filter[ownership]=everything&filter[platform_id]=%d&page=%d' % (self.abf_url, platform_id, page_n)
        d = self.get_page_parser(uri)
        
        bt = d.findAll('table', attrs={'class': 'tablesorter'})[0]
        bl_tags = bt.findAll(attrs={'href': re.compile('/build_lists/')})
        bl_ids = [ x.text for x in bl_tags ]

        return bl_ids
    
    def list_user_groups(self):
        d = self.get_page_parser( self.abf_url + '/groups')
        table = d.find('table', id='myTable')
        res = table.findAll('tr', id='Row1')
        output = []
        for gr in res:
            name = gr.find('a').contents[0]
            descr = gr.find('td', **{'class':'td2'}).contents
            if len(descr) == 0:
                descr = ''
            else:
                descr = descr[0]
            leave = gr.find('td', **{'class':'td5'}).contents
            if len(leave) == 0:
                leave = ''
            else:
                leave = leave[0]
            output.append(dict(name=name, description=descr, leave_url=leave))
        return output
    
    def list_user_platforms(self):
        d = self.get_page_parser( self.abf_url + '/platforms')
        tbody = d.find('table', id='myTable').find('tbody')
        trs = tbody.findAll('tr')
        output = []
        for tr in trs:
            fields = tr.findAll('td')
            name = fields[0].contents[0].contents[0]
            ID = dict(fields[0].contents[0].attrs)['href'][len('/platforms/'):]
            source_type = fields[1].contents[0]
            output.append(dict(name=name, ID=ID, source_type=source_type))
        return output
        
    def get_user_by_name(self, name):
        output = {}
        d = self.get_page_parser('%s/%s' % 
                (self.abf_url, name))
        tmp = d.findAll('h3', text=name)[1].parent.parent
        output['full_name'] = tmp.contents[2].strip()
        output['name'] = name
        
        #project list can be obtained here
        
        return output
        
    def get_project_repositories(self, user_name, project_name):
        d = self.get_page_parser( self.abf_url + '/%s/%s/build_lists/new' %(user_name, project_name))
        output = {
            'save_to_repository':[], 
            }
        
        platforms = d.find('div', {'class':'all_platforms'}).findAll('div', recursive=False, **{'class':'both'})

        for platform in platforms:
            plat_out = {}
            r = platform.find('div', {'class':'build_for_pl'})
            
            plat_out['id'] = dict(r.attrs)['id']
            plat_out['name'] = r.contents[0]

            repos = platform.div.nextSibling.nextSibling.findAll('div')

            plat_out['repositories'] = {}
            for repo in repos:
                repo_out = {}
                inp = repo.find('input')
                label = repo.find('label')

                attrs = dict(inp.attrs)
                repo_out['input_name'] = attrs['name']
                repo_out['value'] = attrs['value']
                if 'disabled' in attrs:
                    repo_out['disabled'] = attrs['disabled']
                else:
                    repo_out['disabled'] = 'enabled'
                repo_out['name'] = attrs['rep_name']
                plat_out['repositories'][repo_out['name']] = repo_out
            output['platforms'][plat_out['name']] = plat_out

        dst_plats = d.find('select', {'id':'build_list_save_to_repository_id'})
        #select_name = dict(dst_plats.attrs)[name]
        opts = dst_plats.findAll('option')
        for opt in opts:
            opt_out = {}
            opt_out['name'] = opt.contents[0]
            opt_out['value'] = dict(opt.attrs)['value']
            output['target_platforms'][opt_out['name']] = opt_out
            
            
        versions = d.find('select', {'id':'build_list_project_version'}).findAll('optgroup')
        branches = versions[0]
        tags = versions[1]
        for opt in branches.findAll('option'):
            opt_out = {}
            opt_out['name'] = opt.contents[0]
            opt_out['value'] = dict(opt.attrs)['value']
            output['versions']['branches'][opt_out['name']] = opt_out
            
        for opt in tags.findAll('option'):
            opt_out = {}
            opt_out['name'] = opt.contents[0]
            opt_out['value'] = dict(opt.attrs)['value']
            output['versions']['tags'][opt_out['name']] = opt_out

        arches = d.findAll('input', {'name':'arches[]'})
        for arch in arches:
            arch_out = {}
            arch_out['name'] = arch.parent.label.contents[0]
            attrs = dict(arch.attrs)
            arch_out['checked'] = attrs['checked']
            arch_out['value'] = attrs['value']
            output['arches'][arch_out['name']] = arch_out
            
        upd_types = d.find('select', {'id':'build_list_update_type'})    
        for opt in upd_types.findAll('option'):
            opt_out = {}
            opt_out['name'] = opt.contents[0]
            opt_out['value'] = dict(opt.attrs)['value']
            output['update_types'][opt_out['name']] = opt_out
            
        meta = d.find('meta', {'content':'authenticity_token', 'name':'csrf-param'}).nextSibling.nextSibling
        seq_token = dict(meta.attrs)['content']
        output['authenticity_token'] = seq_token
        return output

        
