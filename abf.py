#!/usr/bin/python -tt
# -*- coding: UTF-8 -*-

import sys
import argparse
import os
import shutil
from datetime import datetime



from abf.console.config import Config
from abf.console.log import Log
cfg = Config()
log = Log('abf')


from abf.console.misc import *
from abf.api.exceptions import *
from abf.model import *


domain = cfg['main']['domain']
login = cfg['user']['login']
password = cfg['user']['password']
default_group = cfg['user']['default_group']
default_build_platform = cfg['user']['default_build_platform']

#models = Models(domain, login, password)

#r = models.platforms[64]
#r = models.repositories[1]
#r = models.projects[('abf_core', 'abf_core')]
#r = models.projects['akirilenko/libqb']
#r = models.projects['akirilenko/fba']
#r = models.buildlists['715552']
#r = models.arches['1']

#r = models.get_user_platforms_main()
#r = models.get_user_platforms_personal()
#r = models.get_build_platforms()

#r = models.get_arches()

#print r
#print r.repositories

#exit()



def parse_command_line():
    global command_line
    parser = argparse.ArgumentParser(description='ABF Console Client')
    parser.add_argument('-v', '--verbose', action='store_true', help='be verbose')
    parser.add_argument('-c', '--clear-cache', action='store_true', help='clear cached information about repositories, platforms, projects, etc.')
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
    parser_build.add_argument('-p', '--project', action='store', help='project name (can be "group/project")')
    parser_build.add_argument('-b', '--branch', action='store', help='branch to build, can be resolved from repository or target-platform option')
    parser_build.add_argument('-t', '--tag', action='store', help='tag to build')
    parser_build.add_argument('-c', '--commit', action='store', help='Commit hash to build')
    parser_build.add_argument('-s', '--save-to-repository', action='store', help='repository to save results to')
    parser_build.add_argument('-a', '--arches', action='append', help='architectures to build, '
                        'can be set more than once. If not set - use all the available architectures')
    
    parser_build.add_argument('-r', '--repository', action='append', help='repositories to build with (platform/repository). They should all have the same platform.')
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
        
    models = Models(domain, login, password)

    # get project
    if command_line.project:
        tmp = command_line.project.split('/')
        if len(tmp) > 2:
            log.error('The project format is "[owner_name/]project_name"')
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
            log.error('You are not in git repository directory. Specify the project name please!')
            exit(1)
    try:
        proj = models.projects['%s/%s' % (owner_name, project_name)]
    except PageNotFoundError:
        log.error('The project %s/%s does not exists!' % (owner_name, project_name))
        exit(1)
    except ForbiddenError:
        log.error('You do not have acces to the project %s/%s!' % (owner_name, project_name))
        exit(1)
        
    log.debug('Project: %s' % proj)
    if not proj.is_package:
        log.error('The project %s is not a package and can not be built.' % proj)
        exit(1)
        
    
    # get architectures
    arches = []
    all_arches = models.get_arches()
    if command_line.arches:
        for arch in command_line.arches:
            a = models.arches.get_string_key(arch)
            if not a:
                log.error("Invalid architecture: %s" % arch)
                exit(1)
            arches.append(a)
    else:
        arches = all_arches
        log.info("Arches are assumed to be " + str(arches))

    log.debug('Architectures: %s' % arches)
    
    
    # get git commit hash
    tag_def = bool(command_line.tag)
    branch_def = bool(command_line.branch)
    commit_def = bool(command_line.commit)
    
    tmp = tag_def + branch_def + commit_def
    commit_hash = None
    if tmp == 0:
        # here we are either in git directory or specified the project name
        h = get_current_commit_hash()
        if h:
          commit_hash = h
        else:
          pass #TODO: get default branch hash  
            
    elif tmp == 1:
        #resolve the comit hash if needed
        if commit_def:
            commit_hash = command_line.commit
        else:
            #TODO get git repo, get hash
            pass
    else:
        log.error("You should specify ONLY ONE of the following options: branch, tag or commit.")
        exit(1)
    log.debug('Git commit hash: %s' % commit_hash)
    
    # get save-to repository
    save_to_repository = None
    build_for_platform = None
    if command_line.save_to_repository:
        available_repos = proj.repositories
        
        items = command_line.save_to_repository.split('/')
        if len(items) == 2:
            repo_name = items[1]
            pl_name = items[0]
        elif len(items) == 1:
            repo_name = items[0]
            pl_name = default_group + '_personal'
            log.info("Save-to platform is assumed to be " + pl_name)
        elif len(items) == 0:
            pl_name = default_group + '_personal'
            repo_name = 'main'
            log.info("Save-to repository is assumed to be %s/%s" % (pl_name, repo_name))
        else:
            log.error("save-to-repository option format: [platform/]repository")
            exit(1)
        pls = []
        for repo in available_repos:
            if repo.platform.name == pl_name:
                build_for_platform = repo.platform
            pls.append(repo.platform.name)
        if not build_for_platform:
            log.error("Can not build for platform %s. Select one of the following:\n%s" % (pl_name, ', '.join(pls)))
            exit(1)
            
        for repo in build_for_platform.repositories:
            if repo.name == repo_name:
                save_to_repository = repo
                break
        
        if not save_to_repository:
            log.error("Incorrect save-to repository %s/%s.\nSelect one of the following:\n%s" % (pl_name, repo_name, 
                    ', '.join([str(x) for x in build_for_platform.repositories])))
            exit(1)
    else:
        # repository have not been selected, try to resolve it
        pass # TODO: 
    log.debug('Save-to repository: ' + str(save_to_repository))
    
    build_platforms = models.get_build_platforms()
    build_platform_names = [x.name for x in build_platforms]
    build_repositories = []
    if command_line.repository:
        for repo in command_line.repository:
            items = repo.split('/')
            if len(items) == 2:
                repo_name = items[1]
                pl_name = items[0]
            elif len(items) == 1:
                repo_name = items[0]
                pl_name = default_build_platform 
                log.info("Platform for selected repository %s is assumed to be %s" % (repo_name, pl_name))
            else:
                log.error("'repository' option format: [platform/]repository")
                exit(1)
            
            if pl_name not in build_platform_names:
                log.error("Can not build for platform %s!\nSelect one of the following:\n%s" % (pl_name,
                        ', '.join(build_platform_names)))
                exit(1)
            for pl in build_platforms:
                if pl.name == pl_name:
                    build_platform = pl
                    break
            build_repo = None
            for repo in build_platform.repositories:
                if repo.name == repo_name:
                    build_repo = repo
                    break
            if not build_repo:
                log.error("Platform %s does not have repository %s!\nSelect one of the following:\n%s" % (pl_name, repo_name,
                        ', '.join([x.name for x in build_platform.repositories])))
                exit(1)
            build_repositories.append(build_repo)
        

    log.debug("Build repositories: " + str(build_repositories))
    
    BuildList.new_build_task(models, proj, save_to_repository, build_repositories, commit_hash, BuildList.update_types[0], False, arches)
    
    
    
def buildstatus():
    log.debug('BUILDSTATUS started')
    if not command_line.ID:
        log.error("Enter the ID, please. It can not be resolved automatically now (not implemented).")
        exit(1)
    try:
        models = Models(domain, login, password)
        bl = models.buildlists[command_line.ID]
    except ApiException:
        exit(3)
    print '%-20s%s' %('Owner:', bl.owner['name'])
    print '%-20s%s' %('Status:', BuildList.status_by_id[bl.status])
    print '%-20s%s' %('Build for platform:', bl.build_for_platform)
    print '%-20s%s' %('Save to repository:', bl.save_to_repository)
    print '%-20s%s' %('Build repositories:', bl.include_repos)
    print '%-20s%s' %('Architecture:', bl.arch.name)
    print '%-20s%s' %('Created at:', datetime.fromtimestamp(float(bl.created_at)))
    print '%-20s%s' %('Updated at:', datetime.fromtimestamp(float(bl.updated_at)))
    

if __name__ == '__main__':
    parse_command_line()
    if command_line.verbose:
        Log.set_verbose()
    if command_line.clear_cache:
        Models.clear_cache()
    command_line.func()
