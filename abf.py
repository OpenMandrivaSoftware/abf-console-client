#!/usr/bin/python -tt
# -*- coding: UTF-8 -*-

import sys
import argparse
from argparse import RawDescriptionHelpFormatter
import os
import shutil
import pdb



from abf.console.config import Config
from abf.console.log import Log
cfg = Config()
projects_cfg = Config(conf_path='~/.abf_projects', main_conf=False)
log = Log('abf')


from abf.console.misc import *
from abf.api.exceptions import *
from abf.model import *


abf_url = cfg['main']['abf_url']
file_store_url = cfg['main']['file_store_url']
login = cfg['user']['login']
password = cfg['user']['password']
default_group = cfg['user']['default_group']
default_build_platform = cfg['user']['default_build_platform']
models_params = ((abf_url, file_store_url, login, password))

models = Models(*models_params)

#r = models.jsn.upload_file('/tmp/log')

#r = Group(models, 2)
#r = Platform(models, init_data={'id':64, 'name': 'AAAA'})
#r = models.platforms[64]
#r = Platform(models, ID=64)
#r = Repository(models, ID=71)

#r = Project.get_by_name(models, 'import/mock-urpm')

#r = BuildList(models, ID=750988)

#r = models.get_user_platforms_main()
#r = models.get_user_platforms_personal()
#r = models.get_build_platforms()

#r = models.get_arches()

#print r.repositories[0].platform.repositories[2].platform

#exit()
   


def parse_command_line():
    global command_line
    parser = argparse.ArgumentParser(description='ABF Console Client')
    parser.add_argument('-v', '--verbose', action='store_true', help='be verbose, display even debug messages')
    parser.add_argument('-c', '--clear-cache', action='store_true', help='clear cached information about repositories, platforms, projects, etc.')
    parser.add_argument('-q', '--quiet', action='store_true', help='Do not display info messages')
    subparsers = parser.add_subparsers(title='command')
    
    # help
    parser_help = subparsers.add_parser('help', help='show a help for command')
    parser_help.add_argument('command', action='store', nargs='?', help='a command to show help for')
    parser_help.set_defaults(func=help)
    
    # get
    parser_get = subparsers.add_parser('get', help='clone a project from ABF')
    parser_get.add_argument('project', action='store', help='project name. ([group/]project). If no group specified, '
            'it\'s assumed to be your default group.')
    parser_get.add_argument('-b', '--branch', action='store', help='branch to checkout')
    parser_get.set_defaults(func=get)
    
    # put
    parser_put = subparsers.add_parser('put', help='Upload large binary files to File-Store, commit all the changes (git add --all), commit with a message specified and push')
    parser_put.add_argument('-m', '--message', action='store', help='A message to commit with. It is ignored in case of "--do-not-upload"')
    parser_put.add_argument('-u', '--upload-only', action='store_true', help='Upload large files to file-store and exit')
    parser_put.add_argument('-d', '--do-not-upload', action='store', help='Do nothing with .abf.yml, just add, commit and push')
    parser_put.add_argument('-s', '--minimal-file-size', default='2M', action='store', help='The minimal file size to upload to File-Store. '
            'Default is 2M. You can set it to 0 to upload all the files.')
    parser_put.add_argument('-r', '--do-not-remove-files', action='store_true', help='By default files are being removed on uploading. Override this behavior.')
    parser_put.set_defaults(func=put)
    
    # fetch
    parser_fetch = subparsers.add_parser('fetch', help='Download all the files listed in .abf.yml from File-Store to local directory.')
    parser_fetch.add_argument('-o', '--only', action='store', nargs='+', help='Limit the list of downloaded files to this file name(s). This option can be specified more than once.')
    parser_fetch.set_defaults(func=fetch)
    
    # show
    parser_show = subparsers.add_parser('show', help='show some general information. Bash autocomplete uses it.')
    show_choices = ['build-repos', 'build-platforms', 'save-to-repos', 'save-to-platforms']
    parser_show.add_argument('type', action='store', choices=show_choices,help='The type of information to show')
    parser_show.add_argument('-p', '--project', action='store',  help='Project to show information for (if needed). Format: '
        '"[group/]name". If no group specified, default group will be used.')
    parser_show.set_defaults(func=show)
    
    # locate
    parser_locate = subparsers.add_parser('locate', help='tool can remember the project location and use it for some reasons (abfcd, etc.).',
    epilog='Every interaction with git repository (build, get, put, etc.) updates the cached location of the project (overriding '
    'an existing one if needed). For any cached project you can execute "abfcd <project>" and you will cd to the project directory.')
    locate_choices = ['update', 'update-recursive']
    parser_locate.add_argument('action', action='store', choices=locate_choices, nargs='?', help='The type of information to show')
    parser_locate.add_argument('-p', '--project', action='store',  help='Project to show information for (if needed). Format: '
        '"[group/]name". If no group specified, default group will be used.')
    parser_locate.add_argument('-d', '--directory', action='store',  help='Directory to update locations for. It should be a '
            'git repository for "update" and any directory for "update-recursive". If not specified - the current directory will be used')
    parser_locate.set_defaults(func=locate)
    
    # build
    parser_build = subparsers.add_parser('build', help='Initiate a build task on ABF.', formatter_class=RawDescriptionHelpFormatter,
        epilog= 'NOTES:\n'
        'API takes git commit hash to build. So client have to resolve it.\n'
        '1) If you\'ve specified commit hash - it will be used "as is".\n'
        '2) If you\'ve specified branch or tag name - it will be resolved automatically\n'
        'using ABF API. (the hash of top commit will be used for branch)\n'
        '3) If you\'ve specified no git commit related options and you\'ve\n'
        ' specified a project name - this project\'s default branch will be used.\n'
        '4) If you\'ve specified no git commit related options and you\'ve\n'
        'not specified a project name (you have to be in a git repository) -\n'
        'the top remote commit of your current branch will be used.\n')
    parser_build.add_argument('-p', '--project', action='store', help='project name ([group/]project). If no group '
        'specified, it is assumed to be your default group. If the option is not specified and you are in a git '
        'repository directory - resolve a project name from it.')
    parser_build.add_argument('-b', '--branch', action='store', help='branch to build.')
    parser_build.add_argument('-t', '--tag', action='store', help='tag to build.')
    parser_build.add_argument('-c', '--commit', action='store', help='commit sha hash to build.')
    parser_build.add_argument('-s', '--save-to-repository', action='store', help='repository to save results to '
        '([platform/]repository). If no platform part specified, it is assumed to be "<default_group>_personal". '
        'If this option is not specified at all, "<default_group>_personal/main" will be used.')
    parser_build.add_argument('-a', '--arch', action='append', help='architectures to build, '
                        'can be set more than once. If not set - use all the available architectures.')   
    parser_build.add_argument('-r', '--repository', action='append', help='repositories to build with ([platform/]repository). '
        'Can be set more than once. If no platform part specified, it is assumed to be your "<default_build platform>".'
        ' If no repositories were specified at all, use the "main" repository from save-to platform.')
    parser_build.add_argument('--auto-publish', action='store_true', help='enable automatic publishing.')
    upd_types = ['security', 'bugfix', 'enhancement', 'recommended', 'newpackage']
    parser_build.add_argument('--update-type', action='store', choices=upd_types, help='Update type. Default is "%s".' %
                    (BuildList.update_types[0]) )
    parser_build.add_argument('--skip-spec-check', action='store_true', help='Do not check spec file.' )
    parser_build.set_defaults(func=build)
    
    # publish
    parser_publish = subparsers.add_parser('publish', help='Publish the task that have already been built.')
    parser_publish.add_argument('task_ids', action='store', nargs="+", help='The IDs of tasks to publish.')
    parser_publish.set_defaults(func=publish)
    
    # backport
    parser_backport = subparsers.add_parser('backport', help='Copy all the files from SRC_BRANCH to DST_BRANCH')
    parser_backport.add_argument('src_branch', action='store', help='source branch')
    parser_backport.add_argument('dst_branch', action='store', nargs='?', help='destination branch. If not specified, it\'s assumed to be the current branch')
    parser_backport.add_argument('-p', '--pack', action='store_true', help='Create a tar.gz from the src_branch and put this archive and spec file to dst_branch')
    parser_backport.set_defaults(func=backport)
    
    # buildstatus
    parser_clean = subparsers.add_parser('buildstatus', help='get a build-task status', epilog='If a project specified '
    ' or you are in a git repository - try to get the IDs from the last build task sent for this project. If you are not'
    ' in a git repository directory and project is not specified - try to get build IDs from the last build you\'ve done '
    'with console client.')
    parser_clean.add_argument('ID', action='store', nargs='*', help='build list ID')
    parser_clean.add_argument('-p', '--project', action='store',  help='Project. If last IDs for this project can be found - use them')
    parser_clean.add_argument('-s', '--short', action='store_true',  help='Show one-line information including id, project, '
                                                                                                        'arch and status')
    parser_clean.set_defaults(func=buildstatus)
    
    # clean
    parser_clean = subparsers.add_parser('clean', help='Analyze spec file and show missing and unnecessary files from '
                                                                            'the current git repository directory.')
    parser_clean.add_argument('--auto-remove', action='store_true', help='automatically remove all the unnecessary files')
    parser_clean.set_defaults(func=clean)
    
    command_line = parser.parse_args(sys.argv[1:])

def help():
    if command_line.command:
        sys.argv = [sys.argv[0], command_line.command, '-h']
    else:
        sys.argv = [sys.argv[0], '-h']
    parse_command_line()
    
def get_project_name_only(must_exist=True, name=None):
    if name:
        tmp = name.split('/')
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
            if must_exist:
                log.error('You are not in a git repository directory. Specify the project name please!')
                exit(1)
            else:
                return None
        _update_location()
    return (owner_name, project_name)

def get_project(models, must_exist=True, name=None):
    
    owner_name, project_name = get_project_name_only(must_exist, name)
    try:
        proj = Project.get_by_name(models, '%s/%s' % (owner_name, project_name))
    except PageNotFoundError:
        log.error('The project %s/%s does not exist!' % (owner_name, project_name))
        exit(1)
    except ForbiddenError:
        log.error('You do not have acces to the project %s/%s!' % (owner_name, project_name))
        exit(1)
        
    log.debug('Project: %s' % proj)
    return proj
    
    
def get():
    log.debug('GET started')
    proj = command_line.project
    tmp = proj.split('/')
    if len(tmp) > 2:
        log.error('Specify a project name as "group_name/project_name" or just "project_name"')
        exit(1)
    elif len(tmp) == 1:
        project_name = proj
        proj = '%s/%s' % (cfg['user']['default_group'], proj)
    elif len(tmp) == 2:
        project_name = tmp[1]
    
    uri = "%s/%s.git" % (cfg['user']['git_uri'], proj)
    cmd = ['git', 'clone', uri]
    if command_line.branch:
        cmd += ['-b', command_line.branch]
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    
    projects_cfg[proj]['location'] = os.path.join(os.getcwd(), project_name)

def put():
    log.debug('PUT started')
    
    if not command_line.upload_only and not command_line.message:
        log.error("Specify a message first!")
        exit(1)
        
    if command_line.upload_only and command_line.do_not_upload:
        log.error("Conflicting options: --upload-only and --do-not-upload" )
        exit(1)
        
    path = get_root_git_dir()
    yaml_path = os.path.join(path, '.abf.yml')
    if not path:
        log.error("You have to be in a git repository directory")
        exit(1)
    _update_location()
    
    if not command_line.do_not_upload:
        try:
            min_size = human2bytes(command_line.minimal_file_size)
        except ValueError, ex:
            log.error('Incorrect "--minimal-file-size" value: %s' % command_line.minimal_file_size)
            exit(1)
        error_count = upload_files(models, min_size, remove_files=not command_line.do_not_remove_files, path=path)
        if error_count:
            log.info('There were errors while uploading, stopping.')
            return
    
    if command_line.upload_only:
        return

    cmd = ['git', 'add', '--all']
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    
    if os.path.isfile(yaml_path):
        cmd = ['git', 'add', '-f', path]
        execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    
    cmd = ['git', 'commit', '-m', command_line.message]
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    
    log.info('Commited.')
    cmd = ['git', 'push']
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    log.info('Pushed')

def fetch():
    log.debug('FETCH started')
    path = get_root_git_dir()
    if not path:
        log.error("You have to be in a git repository directory")
        exit(1)
    path = os.path.join(path, '.abf.yml')
    if not os.path.isfile(path):
        log.error('File "%s" can not be found')
        exit(1)
    fetch_files(models, path, command_line.only)

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
    
    _update_location(path=path)

    stage = 0
    try:
        if start_branch != dbrn:
            cmd = ['git', 'checkout', dbrn]
            execute_command(cmd, print_to_stdout=True, cwd=path)
        stage = 1
        cmd = ['rm', '-rf', './*']
        execute_command(cmd, print_to_stdout=True, cwd=path)
        stage = 2
        cmd = ['git', 'checkout', sbrn, '*']
        execute_command(cmd, print_to_stdout=True, cwd=path)
        stage = 3
        if command_line.pack:
            pack_project(path)
            cmd = ['git', 'reset']
            execute_command(cmd, print_to_stdout=True, cwd=path)
    except Exception, ex:
        if type(ex) == ReturnCodeNotZero:
            log.error(str(ex))
        else:
            log.exception(ex)
            
        if stage == 1 or stage == 2:
            log.info("Checking out the initial branch (%s)" % start_branch)
            cmd = ['git', 'reset', '--hard', start_branch]
            execute_command(cmd, print_to_stdout=True, cwd=path)

    log.info('Done')
    
def build():
    log.debug('BUILD started')
    
    IDs = {
            'arches':[],
            'version':None,
            'target_platform':None,
            'repositories':[],
        }
        
    # get project
    proj = get_project(models, must_exist=True, name=command_line.project)
    if not command_line.project and not command_line.skip_spec_check: # local git repository
        find_spec_problems()
    if not proj.is_package:
        log.error('The project %s is not a package and can not be built.' % proj)
        exit(1)
    
    # get architectures
    arches = []
    all_arches = Arch.get_arches(models)
    if command_line.arch:
        for arch in command_line.arch:
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
        if command_line.project:
            command_line.branch = proj.default_branch
        else: # we are in a git repository and it the project we are building
            command_line.branch = get_branch_name()
        log.info('The git branch is assumed to be "%s"' % command_line.branch)
        branch_def = True
        tmp = 1
    if tmp == 1:
        if commit_def:
            commit_hash = command_line.commit
        else:
            to_resolve = command_line.branch or command_line.tag
            ref_type = (branch_def and 'commit') or (tag_def and 'tag')
            refs = proj.get_refs_list(models)
            for ref in refs:
               
                if ref['ref'] == to_resolve and ref['object']['type'] == ref_type:
                    commit_hash = ref['object']['sha']
            if commit_hash == None:
                log.error("Could not resolve hash for %s '%s'" % (ref_type, to_resolve))
                exit(1)
    if tmp > 1:
        log.error("You should specify ONLY ONE of the following options: branch, tag or commit.")
        exit(1)
    log.debug('Git commit hash: %s' % commit_hash)
    
    # get save-to repository
    save_to_repository = None
    build_for_platform = None

    available_repos = proj.repositories
    
    if command_line.save_to_repository:
        items = command_line.save_to_repository.split('/')
    else:
        items = []
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
        
    log.debug('Save-to repository: ' + str(save_to_repository))
    
    
    # get the list of build repositories
    build_platforms = Platform.get_build_platforms(models)
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
                log.error("Can not connect repositories from %s!\nSelect one of the following:\n%s" % (pl_name,
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
    else:
        build_platform = save_to_repository.platform
        
        if build_platform.name not in build_platform_names or not build_platform.repositories:
            log.error("Could not resolve repositories to build with. Please specify it (-r option)")
            exit(1)
        
        for repo in build_platform.repositories:
            if repo.name == 'main':
                log.info("The repository to build with is assumed to be " + str(repo))
                build_repositories = [repo]

    if not build_repositories:
        log.error("You have to specify the repository(s) to build with (-r option)")
        exit(1)
        
    log.debug("Build repositories: " + str(build_repositories))
    build_ids = BuildList.new_build_task(models, proj, save_to_repository, build_repositories, commit_hash, 
            command_line.update_type or BuildList.update_types[0], command_line.auto_publish, arches)
    ids = ','.join([str(i) for i in build_ids])
    projects_cfg['main']['last_build_ids'] = ids
    projects_cfg[str(proj)]['last_build_ids'] = ids
    
def publish():
    log.debug('PUBLISH started')
    for task_id in command_line.task_ids:
        try:
            bl = BuildList(models, task_id)
            if bl.status != 0:
                log.error("The status of build task %s is \"%s\", can not publish it!" % (bl.id, bl.status_string))
                continue
            res = bl.publish()
        except AbfApiException, ex:
            log.error('Could not publish task %s: %s' %(task_id, str(ex)))


def _print_build_status(models, ID):
    try:
        bl = BuildList(models, ID)
    except AbfApiException, ex:
        log.error("Can not read buildlist %s: %s" % (ID, ex))
        exit(3)
    if command_line.short:
        print repr(bl)
    else:
        print '%-20s%s' %('Buildlist ID:', bl.id) 
        print '%-20s%s' %('Owner:', bl.owner.uname)
        print '%-20s%s' %('Project:', bl.project.fullname)
        print '%-20s%s' %('Status:', bl.status_string)
        print '%-20s%s' %('Build for platform:', bl.build_for_platform)
        print '%-20s%s' %('Save to repository:', bl.save_to_repository)
        print '%-20s%s' %('Build repositories:', bl.include_repos)
        print '%-20s%s' %('Architecture:', bl.arch.name)
        print '%-20s%s' %('Created at:', bl.created_at)
        print '%-20s%s' %('Updated at:', bl.updated_at)
        print ''
            
def buildstatus():
    log.debug('BUILDSTATUS started')
    ids = []
    if command_line.ID:
        ids = command_line.ID
        
    res = get_project_name_only(must_exist=False, name=command_line.project)
    if res:
        proj = '%s/%s' % res
        ids += projects_cfg[proj]['last_build_ids'].split(',')
    elif not command_line.ID:
        if 'main' not in projects_cfg or 'last_build_ids' not in projects_cfg['main']:
            log.error("Can not find last build IDs. Specify a project name or ID")
            exit(1)
        ids += projects_cfg['main']['last_build_ids'].split(',')
            
    ids = list(set(ids))
    for i in ids:
        _print_build_status(models, i)
        
    
    
def _update_location(path=None, silent=True):
    try:
        if not path:
            path = os.getcwd()
        log.debug("Updating project location for %s" % path)
        group, name = get_project_name(path)
        if group:
            proj = '%s/%s' % (group, name)
            projects_cfg[proj]['location'] = path
            text = "Project %s has been located in %s" % (proj, path)
            if silent:
                log.debug(text)
            else:
                log.info(text)
    except:
        pass

def _update_location_recursive(path):
    items = os.listdir(path)
    if '.git' in items: # it's a git directory!
        _update_location(path, silent=False)
        return
    
    for item in items:
        item_path = os.path.join(path, item)
        if not os.path.isdir(item_path) or os.path.islink(item_path):
            continue
        _update_location_recursive(item_path)
        
        
def locate():
    log.debug('LOCATE started')
    
    if not command_line.action: # show location
        if not command_line.project:
            print "To show a project location, you have to specify a project name ('-p' option)"
            return
        
        tmp = command_line.project.split('/')
        if len(tmp) > 2:
            log.error('error: the project format is "[owner_name/]project_name"')
            exit(1)
        elif len(tmp) == 1:
            proj = '%s/%s' % (default_group, tmp[0])
        else: # len == 2
            proj = command_line.project
            
        if proj not in projects_cfg or 'location' not in projects_cfg[proj] or not projects_cfg[proj]['location']:
            print 'error: project %s can not be located' % proj
            exit(1)
        path = projects_cfg[proj]['location']
        if not os.path.isdir(path):
            print 'error: project is not located in "%s" anymore' % path
            projects_cfg[proj]['location'] = ''
            exit(1)
        print path
        return
    else:
        if command_line.action == 'update':
            path = command_line.directory or os.getcwd()
            _update_location(path)
        elif command_line.action == 'update-recursive':
            path = command_line.directory or os.getcwd()
            _update_location_recursive(path)
    
def show():
    log.debug('SHOW started')
    Log.set_silent()
    t = command_line.type

    if t in ['build-platforms', 'build-repos']:
        build_platforms = Platform.get_build_platforms(models)
        platform_names = []
        repo_names = []
        for plat in build_platforms:
            if plat.repositories:
                platform_names.append(plat.name)
            for repo in plat.repositories:
                repo_names.append(str(repo))
        out = (t == 'build-platforms' and platform_names) or (t == 'build-repos' and repo_names)
            
    if t in ['save-to-platforms', 'save-to-repos']:
        proj = get_project(models, must_exist=True, name=command_line.project)
        repos = proj.repositories
        platform_names = []
        repo_names = []
        for repo in repos:
            platform_names.append(repo.platform.name)
            repo_names.append(str(repo))
        platform_names = list(set(platform_names))
        out = (t == 'save-to-platforms' and platform_names) or (t == 'save-to-repos' and repo_names)
    print ' '.join(out)
    

    
def clean():
    log.debug("CLEAN started")
    _update_location()
    find_spec_problems(auto_remove=command_line.auto_remove)
    

if __name__ == '__main__':
    parse_command_line()

    if command_line.verbose:
        Log.set_verbose()
    if command_line.quiet:
        Log.set_quiet()
    if command_line.clear_cache:
        Models.clear_cache()
    command_line.func()
