#!/usr/bin/python -tt
# -*- coding: UTF-8 -*-

import sys
import argparse
import os
import shutil



from abf.console.config import Config
from abf.console.log import Log
cfg = Config()
log = Log('abf')


from abf.console.misc import *

from abf.model import Models


domain = cfg['main']['domain']
login = cfg['user']['login']
password = cfg['user']['password']
default_group = cfg['user']['default_group']

#models = Models(domain, login, password)
#res = models.platforms['15']
#res = models.platforms['17']
#res = models.repositories[('18', '24')]
#print res
#exit()


def parse_command_line():
    global command_line
    parser = argparse.ArgumentParser(description='ABF Console Client')
    parser.add_argument('-v', '--verbose', action='store_true', help='be verbose')
    subparsers = parser.add_subparsers()
    
    # help
    parser_get = subparsers.add_parser('help', help='show a help for command')
    parser_get.add_argument('command', action='store', nargs='?', help='command to show help for')
    parser_get.set_defaults(func=help)
    
    # get
    parser_get = subparsers.add_parser('get', help='clone a project from ABF')
    parser_get.add_argument('project', action='store', help='project name. (can be "group/project")')
    parser_get.add_argument('-b', '--branch', action='store', help='branch to checkout')
    parser_get.set_defaults(func=get)
    
    # put
    parser_get = subparsers.add_parser('put', help='commit changes (with -am "message") and push')
    parser_get.add_argument('message', action='store', help='a message to commit with')
    parser_get.set_defaults(func=put)
    
    # build
    parser_build = subparsers.add_parser('build', help='Initiate a build task on ABF')
    parser_build.add_argument('project', action='store', nargs='?', help='project name (can be "group/project")')
    parser_build.add_argument('-b', '--branch', action='store', help='branch to build, can be resolved from repository or target-platform option')
    parser_build.add_argument('-t', '--tag', action='store', help='tag to build')
    parser_build.add_argument('-p', '--target-platform', action='store', help='platform to build into, can be resolved from branch or target repository')
    parser_build.add_argument('-a', '--arches', action='append', help='architectures to build, '
                        'can be set more than once. If not set - use all the available architectures')
    
    parser_build.add_argument('-r', '--repository', action='append', help='repositories to build with (platform/repository)')
    parser_build.set_defaults(func=build)
    
    # backport
    parser_build = subparsers.add_parser('backport', help='Copy all the files from SRC_BRANCH to DST_BRANCH, or to the current brunch if not specified.')
    parser_build.add_argument('src_branch', action='store', help='source branch')
    parser_build.add_argument('dst_branch', action='store', nargs='?', help='destination branch')
    parser_build.add_argument('-p', '--pack', action='store_true', help='Create a tar.gz from the src_branch and put this archive and spec file to dst_branch')
    parser_build.set_defaults(func=backport)
    
    # buildstatus
    parser_build = subparsers.add_parser('buildstatus', help='get a building task status')
    parser_build.add_argument('ID', action='store', nargs='?', help='build list ID')
    parser_build.add_argument('-l', '--logs', action='store_true', help='also download logs (not implemented)')
    parser_build.set_defaults(func=buildstatus)
    
    command_line = parser.parse_args(sys.argv[1:])

def help():
    if command_line.command:
        sys.argv = [sys.argv[0], command_line.command, '-h']
    else:
        sys.argv = [sys.argv[0], '-h']
    parse_command_line()

def get():
    log.debug('GET started')
    proj = command_line.project
    tmp = proj.split('/')
    if len(tmp) > 2:
        log.error('Specify a project name as "group_name/project_name" or just "project_name"')
        exit(1)
    if len(tmp) == 1:
        proj = '%s/%s' % (cfg['user']['default_group'], proj)
    
    uri = "%s/%s.git" % (cfg['user']['git_uri'], proj)
    cmd = ['git', 'clone', uri]
    if command_line.branch:
        cmd += ['-b', command_line.branch]
    #log.debug('Executing command ' + str(cmd))
    execute_command(cmd, log=log, print_to_stdout=True, exit_on_error=True)
    
    #os.execlp(*cmd)
    
def put():
    log.debug('PUT started')
    cmd = ['git', 'commit', '-a', '-m', command_line.message]
    execute_command(cmd, log=log, print_to_stdout=True, exit_on_error=True)
    
    log.info('Commited.')
    cmd = ['git', 'push']
    execute_command(cmd, log=log, print_to_stdout=True, exit_on_error=True)
    log.info('Pushed')
    

        
def backport():
    log.debug('BACKPORT started')
    sbrn = command_line.src_branch
    start_branch = get_branch_name()
    if not start_branch:
        log.error("You are not in a git directory")
        exit(1)
    log.debug("Current brunch is " + start_branch)
    if command_line.dst_branch:
        dbrn = command_line.dst_branch
    else:
        dbrn = start_branch
    
    if sbrn == dbrn:
        log.error("Source and destination branches shold be different branches!")
        exit(1)
        
    path = get_root_git_dir()
    log.debug("Repository root folder is " + path)

    stage = 0
    try:
        if start_branch != dbrn:
            cmd = ['git', 'checkout', dbrn]
            execute_command(cmd, log, print_to_stdout=True, cwd=path)
        stage = 1
        cmd = ['rm', '-rf', './*']
        execute_command(cmd, log=log, print_to_stdout=True, cwd=path)
        stage = 2
        cmd = ['git', 'checkout', sbrn, '*']
        execute_command(cmd, log=log, print_to_stdout=True, cwd=path)
        stage = 3
        if command_line.pack:
            pack_project(log, path)
            cmd = ['git', 'reset']
            execute_command(cmd, log=log, print_to_stdout=True, cwd=path)
    except Exception, ex:
        if type(ex) == ReturnCodeNotZero:
            log.error(str(ex))
        else:
            log.exception(ex)
            
        if stage == 1 or stage == 2:
            log.info("Checking out the initial branch (%s)" % start_branch)
            cmd = ['git', 'reset', '--hard', start_branch]
            execute_command(cmd, log=log, print_to_stdout=True, cwd=path)

    log.info('Done')
    
def build():
    log.debug('BUILD started')
    IDs = {
            'arches':[],
            'version':None,
            'target_platform':None,
            'repositories':[],
        }

    
    if command_line.project:
        tmp = command_line.project.split('/')
        if len(tmp) > 2:
            log.error('The project format is "owner_name/project_name"')
            exit(1)
        elif len(tmp) == 1:
            project_name = tmp[0]
            log.info("The project group is assumed to be " + default_group)
            owner_name = default_group
        else: # len == 2
            owner_name = tmp[0]
            project_name = tmp[1]  
    else:
        owner_name, project_name = get_project_name()
        if not project_name:
            log.error('You are not in git repository. Specify the project name!')
            exit(1)
    
    if command_line.branch and command_line.tag:
        log.error('Branch and tag can not be specified simultaneously!')
        exit(1)
            
    log.debug('Project name: %s/%s' % (owner_name, project_name))
    
    models = Models(domain, login, password)
    nbp = models.newbuildpages[(owner_name, project_name)]
    if command_line.arches:
        arches = list(set(command_line.arches))
        
        for arch in arches:
            if arch not in nbp.arches.keys():
                log.error("Error: can not build for arch %s" % arch)
                exit(1)
    else:
        arches = nbp.arches.keys()
        log.info("Arches are assumed to be " + str(arches))
        
    for arch in arches:
        IDs['arches'].append(nbp.arches[arch]['value'])
    log.debug('Architectures: %s' % arches)
    
    # try to resolve a version from branch or tag
    version = None
    if command_line.branch:
        if command_line.branch in nbp.versions['branches']:
            version = command_line.branch
        if 'latest_' + command_line.branch in nbp.versions['branches']:
            version = 'latest_' + command_line.branch
    if command_line.tag:
        if command_line.tag in nbp.versions['tags']:
            version = command_line.tag
    if (command_line.branch or command_line.tag) and not version:
        if command_line.branch:
            log.error('Selected branch (%s) is not correct' % command_line.branch)
        if command_line.tag:
            log.error('Selected tag (%s) is not correct' % command_line.tag)
        exit(1)
    
    # try to resolve a version fromplatform
    if (not command_line.branch and not command_line.tag):
        if not command_line.target_platform:
            log.error('You have to specify either platform or version (tag or branch), or both of them')
            exit(1)
        else:
            plat = command_line.target_platform.split('/')[0]
            if ('latest_' + plat) in nbp.versions['branches']:
                version = 'latest_' + plat
                log.info("Version is assumed to be " + version)
            else:
                log.error("Could not resolve version from platform name")
                exit(1)
            
    log.debug('Version: %s' % version)
    
    # If version is selected via command line and correct, 
    # but platform is not selected
    platform = None
    if version and not command_line.target_platform:
        tmp = version
        if tmp.startswith('latest_'):
            tmp = tmp[7:]
        if tmp + '/main' in nbp.target_platforms:
            platform = tmp + '/main'
            log.info("Target repository to save to is assumed to be " + platform)
            
    if command_line.target_platform:
        tmp = command_line.target_platform.split('/')
        if len(tmp) == 1:
            tmp.append('main')
        elif len(tmp) > 2:
            log.error("Target platform format is 'platform_name' or 'platform_name/project_name'")
            exit(1)
        p = tmp[0] + '/' + tmp[1]
        if p in nbp.target_platforms:
            platform = p
        else:
            log.error("Target platform specified (%s) is not correct!" % (command_line.target_platform))
            exit(1)
    
    log.debug('Platform: %s' % platform)
    
    # try to resolve platform
    if version and not platform:
        log.error('Could not resolve platform. Please, specify it.')
        exit(1)
        
    if not version and platform:
        log.error('Could not resolve version (branch or tag). Please, specify it.')
        exit(1)
        
    #resolve target platform
    IDs['target_platform'] = nbp.target_platforms[platform]['value']
    
    if version in nbp.versions['branches']:
        IDs['version'] = nbp.versions['branches'][version]['value']
    if version in nbp.versions['tags']:
        IDs['version'] = nbp.versions['tags'][version]['value']
    
    repos = []
    
    # try to resolve a repository
    plat = platform.split('/')[0]
    repo = platform.split('/')[1]
    if plat in nbp.platforms and repo in nbp.platforms[plat]['repositories']:
        repos = [(plat, repo)]
    
    if command_line.repository:
        repos = []
        tmp = []
        for repo in command_line.repository:
            if len(repo.split('/')) != 2:
                log.error('Repository format: platform/repository. "%s" is not correct' % repo)
                exit(2)
            p = repo.split('/')[0]
            r = repo.split('/')[1]
            repos.append((p, r))
            if not p in nbp.platforms:
                log.error('Platform specified (%s) is not correct!' % p)
                exit(2)
            if not r in nbp.platforms[p]['repositories']:
                log.error('Repository specified (%s/%s) is not correct!' % (p, r) )
                exit(2)
    if not repos:
        log.error('Repository to build with could not be resolved. Please, specify it.')
        exit(2)
         
    for plat, repo in repos:
        IDs['repositories'].append(nbp.platforms[plat]['repositories'][repo]['value'])
        
    nbp.build(IDs)
    
def buildstatus():
    log.debug('BUILDSTATUS started')
    if not command_line.ID:
        log.error("Enter the ID, please. It can not be resolved automatically now (not implemented).")
        exit(1)
    models = Models(domain, login, password)
    bl = models.buildlists[command_line.ID]
    print '%-20s%s' %('Owner:', bl.owner_name)
    print '%-20s%s' %('Status:', bl.status)
    print '%-20s%s' %('User:', bl.user_name)
    print '%-20s%s' %('Build for platform:', bl.platform)
    print '%-20s%s' %('Repository:', bl.repository)
    print '%-20s%s' %('Architecture:', bl.arch)
    print '%-20s%s' %('Notified at:', bl.notified_at)
    print '%-20s%s' %('Packages:', ', '.join(bl.packages))
    

if __name__ == '__main__':
    parse_command_line()
    if command_line.verbose:
        Log.set_verbose()
    command_line.func()
