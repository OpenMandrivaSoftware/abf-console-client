#!/usr/bin/python -tt
# -*- coding: UTF-8 -*-

import sys
import argparse
from argparse import RawDescriptionHelpFormatter
import os
import shutil
import platform
from glob import glob
import shlex
from subprocess import Popen, PIPE

import tempfile

from abf.console.config import Config, mkdirs
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
default_branch = cfg['user']['default_branch']
models_params = ((abf_url, file_store_url, login, password))

models = Models(*models_params)

configs_dir = '/etc/abf/mock-urpm/configs/'

def test():
    log.debug('TEST started')
    pls_import_personal = Platform.search(models, 'import_personal')
    grs_import = Group.search(models, 'import')
    prs_abfcc = Project.search(models, 'abf-console-client')
    uss_akirilenko = User.search(models, 'akirilenko')

    assert pls_import_personal
    assert grs_import
    assert prs_abfcc
    assert uss_akirilenko

    assert pls_import_personal[0].repositories[0].platform == pls_import_personal[0]

    # check last items
    assert Platform(models, ID=pls_import_personal[0].id).name == pls_import_personal[0].name
    assert Group(models, ID=grs_import[0].id).uname == grs_import[0].uname
    assert Project(models, ID=prs_abfcc[0].id).name == prs_abfcc[0].name
    assert User(models, ID=uss_akirilenko[0].id).uname == uss_akirilenko[0].uname

    # make models load the whole object
    pls_import_personal[0].description
    grs_import[0].description
    prs_abfcc[0].description
    uss_akirilenko[0].professional_experience

    pr_abfcc = Project.get_by_name(models, 'akirilenko/abf-console-client')
    assert pr_abfcc in prs_abfcc

    #bl = BuildList(models, ID=750988)
    Platform.get_user_platforms_main(models)
    Platform.get_user_platforms_personal(models)
    Platform.get_build_platforms(models)

    arches = Arch.get_arches(models)
    arch_x86_64 = Arch.get_arch_by_name(models, 'x86_64')
    assert arch_x86_64 in arches

    log.info('Datamodel seems to work fine')


def apply_aliases():
    # check if the current command is 'alias'
    if 'alias' in sys.argv:
        ind = sys.argv.index('alias')
        found = False
        for i in range(1, ind):
            if sys.argv[i] not in ['-h', '-v', '--help', '--verbose', 'help']:
                found = True
        if not found:
            return
    for alias_name in cfg['alias']:
        alias = shlex.split(cfg['alias'][alias_name])
        if alias_name in sys.argv:
            ind = sys.argv.index(alias_name)
            del sys.argv[ind]
            for item in alias:
                sys.argv.insert(ind, item)
                ind += 1


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

    # alias
    parser_alias = subparsers.add_parser('alias', help='Manage aliases')
    alias_commands = ['list', 'add', 'remove']
    parser_alias.add_argument('command', action='store', choices=alias_commands)
    parser_alias.add_argument('options', action='store', nargs='*', help='name and alias (not quoted, e. g. "abf alias add sg search groups") for adding, only name for removing.')
    parser_alias.set_defaults(func=alias)

    # get
    parser_get = subparsers.add_parser('get', help='clone a project from ABF')
    parser_get.add_argument('project', action='store', help='project name. ([group/]project). If no group specified, '
            'it\'s assumed to be your default group.')
    parser_get.add_argument('-b', '--branch', action='store', help='branch to checkout')
    parser_get.set_defaults(func=get)

    # put
    parser_put = subparsers.add_parser('put', help='Upload large binary files to File-Store and update (or create) .abf.yml file. Can also commit and push changes.')
    parser_put.add_argument('-m', '--message', action='store', help='With this option specified, "git add --all", "git commit -m MSG" and "git push" will be executed.')
    parser_put.add_argument('-s', '--minimal-file-size', default='0', action='store', help='The minimal file size to upload to File-Store. '
            'Default is 0B.')
    parser_put.add_argument('-n', '--do-not-remove-files', action='store_true', help='By default files are being removed on uploading. Override this behavior.')
    parser_put.add_argument('-u', '--upload-only', action='store_true', help='Deprecated! Affects nothing. Saved for compatibility reasons and will be removed later.')
    parser_put.set_defaults(func=put)

    # store
    parser_store = subparsers.add_parser('store', help='Upload a given file to File-Store. Prints a sha1 hash or error message (with non-zero return code).')
    parser_store.add_argument('path', action='store', help='Path to file')
    parser_store.set_defaults(func=store)

    # fetch
    parser_fetch = subparsers.add_parser('fetch', help='Download all the files listed in .abf.yml or file with given hash from File-Store to local directory.')
    parser_fetch.add_argument('filehash', action='store', help='Download file with given hash')
    parser_fetch.add_argument('-o', '--only', action='append', help='Limit the list of downloaded files to this file name(s). This option can be specified more than once.')
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
        'Can be set more than once. If no platform part specified, it is assumed to be your "<default_build_platform>".'
        ' If no repositories were specified at all, use the "main" repository from save-to platform.')
    parser_build.add_argument('--auto-publish', action='store_true', help='deprecated synonym for --auto-publish-status=default.')
    parser_build.add_argument('--auto-publish-status', action='store', choices=BuildList.auto_publish_statuses, help='enable automatic publishing. Default is "%s".' %
                    (BuildList.auto_publish_statuses[0]))
    parser_build.add_argument('--skip-personal', action='store_true', help='do not use personal repository to resolve dependencies.')
    parser_build.add_argument('--auto-create-container', action='store_true', help='enable automatic creation of container')
    parser_build.add_argument('--update-type', action='store', choices=BuildList.update_types, help='Update type. Default is "%s".' %
                    (BuildList.update_types[0]) )
    parser_build.add_argument('--skip-spec-check', action='store_true', help='Do not check spec file.' )
    parser_build.set_defaults(func=build)

    # mock-urpm
    parser_mock_urpm = subparsers.add_parser('mock-urpm', help='Build a project locally using mock-urpm.', epilog='No checkouts will be made,'
                                                                    'the current git repository state will be used')
    parser_mock_urpm.add_argument('-c', '--config', action='store', help='A config template to use. Specify owne of the config names '
        'from %s. Directory path should be omitted. If no config specified, "default.cfg" will be used' % configs_dir)
    parser_mock_urpm.set_defaults(func=localbuild_mock_urpm)

    # rpmbuild
    parser_rpmbuild = subparsers.add_parser('rpmbuild', help='Build a project locally using rpmbuild.', epilog='No checkouts will be made,'
                                                                    'the current git repository state will be used')
    parser_rpmbuild.add_argument('-b', '--build', action='store', choices=['b', 's', 'a'], default='a', help='Build src.rpm (s), rpm (b) or both (a)')
    parser_rpmbuild.set_defaults(func=localbuild_rpmbuild)

    # publish
    parser_publish = subparsers.add_parser('publish', help='Publish the task that have already been built.')
    parser_publish.add_argument('task_ids', action='store', nargs="+", help='The IDs of tasks to publish.')
    parser_publish.set_defaults(func=publish)

    # copy
    parser_copy = subparsers.add_parser('copy', help='Copy all the files from SRC_BRANCH to DST_BRANCH')
    parser_copy.add_argument('src_branch', action='store', help='source branch')
    parser_copy.add_argument('dst_branch', action='store', nargs='?', help='destination branch. If not specified, it\'s assumed to be the current branch')
    parser_copy.add_argument('-p', '--pack', action='store_true', help='Create a tar.gz from the src_branch and put this archive and spec file to dst_branch')
    parser_copy.set_defaults(func=copy)

    # pull request
    parser_pull = subparsers.add_parser('pullrequest', help='Send a pull request from SRC_BRANCH to DST_BRANCH')
    parser_pull.add_argument('from_ref', action='store', help='source ref or branch')
    parser_pull.add_argument('to_ref', action='store', help='destination ref or branch')
    parser_pull.add_argument('title', action='store', help='Request title')
    parser_pull.add_argument('body', action='store', help='Request body')
    parser_pull.add_argument('-p', '--project', action='store', help='project name (group/project).')
    parser_pull.set_defaults(func=pull_request)

    # fork project
    parser_pull = subparsers.add_parser('fork', help='Fork existing project')
    parser_pull.add_argument('source_project', action='store', help='project to fork (group/project)')
    parser_pull.add_argument('target_project', action='store', nargs='?', help='target project group and name (group/project)')
    parser_pull.set_defaults(func=fork_project)

    # create project from SRPM
    parser_pull = subparsers.add_parser('create', help='Create project from SRPM')
    parser_pull.add_argument('srpm', action='store', help='srpm file')
    parser_pull.add_argument('owner', action='store', nargs='?', help='who will own the project; default_owner is used by default')
    parser_pull.add_argument('-b', '--branch', action='append', help='create additional branch; can be set more than once.')
    parser_pull.add_argument('--no-def-branch', action='store_true', help='Do not automatically create branch set as default in user config (if it is set to smth different from "master").')
    parser_pull.set_defaults(func=create)

    # add project to repository
    parser_pull = subparsers.add_parser('add', help='Add project to specified repository')
    parser_pull.add_argument('repository', action='store', help='target repository ([platform/]repository)')
    parser_pull.add_argument('-p', '--project', action='store', help='project name (group/project).')
    parser_pull.set_defaults(func=add_project_to_repository)

    # remove project from repository
    parser_pull = subparsers.add_parser('remove', help='Remove project from specified repository')
    parser_pull.add_argument('repository', action='store', help='target repository ([platform/]repository)')
    parser_pull.add_argument('-p', '--project', action='store', help='project name (group/project).')
    parser_pull.set_defaults(func=remove_project_from_repository)

    # status
    parser_status = subparsers.add_parser('status', help='get a build-task status', epilog='If a project specified '
    ' or you are in a git repository - try to get the IDs from the last build task sent for this project. If you are not'
    ' in a git repository directory and project is not specified - try to get build IDs from the last build you\'ve done '
    'with console client.')
    parser_status.add_argument('ID', action='store', nargs='*', help='build list ID')
    parser_status.add_argument('-p', '--project', action='store',  help='Project. If last IDs for this project can be found - use them')
    parser_status.add_argument('-s', '--short', action='store_true',  help='Show one-line information including id, project, '
                                                                                                        'arch and status')
    parser_status.set_defaults(func=status)

    # clean
    parser_clean = subparsers.add_parser('clean', help='Analyze spec file and show missing and unnecessary files from '
                                                                            'the current git repository directory.')
    parser_clean.add_argument('--auto-remove', action='store_true', help='automatically remove all the unnecessary files')
    parser_clean.set_defaults(func=clean)

    # search
    parser_search = subparsers.add_parser('search', help='Search for something on ABF.', epilog='NOTE: only first 100 results of any request will be shown')
    search_choices = ['users', 'groups', 'platforms', 'projects']
    parser_search.add_argument('type', action='store', choices=search_choices, help='what to search for')
    parser_search.add_argument('query', action='store', help='a string to search for')
    parser_search.set_defaults(func=search)

    #list

    # info
    parser_info = subparsers.add_parser('info', help='get information about single instance')
    info_choices = ['platforms', 'repositories', 'projects']
    parser_info.add_argument('type', action='store', choices=info_choices, help='type of the instance')
    parser_info.add_argument('-f', '--filter', action='store', help='The filter may be specified by defining multiple pairs <type>.<attribute>=<value> or <attribute>=<value>, where <type> is one of the following positional arguments: %s, <attribute> is the one of the instance fields or special attribute (page - using for pagination) and <value> - string, that can take asterisk (*) or anything else... Example: abf info projects -f platforms.name=rosa2012lts page=*' % info_choices, nargs='*')
    parser_info.add_argument('-o', '--output', action='store', help='output format ', nargs='*')
    parser_info.set_defaults(func=info_single)

    # test
    parser_test = subparsers.add_parser('test', help='Execute a set of internal datamodel tests')
    parser_test.set_defaults(func=test)

    for s in subparsers._name_parser_map:
        subparsers._name_parser_map[s].add_argument('-v', '--verbose', action='store_true', help='be verbose, display even debug messages')

    command_line = parser.parse_args(sys.argv[1:])


def info_single():
    st = command_line.type
    cl = {'platforms': Platform, 'repositories': Repository, 'projects': Project}
    if not command_line.filter:
        log.debug('Filter can be specified with the following parameters:\n %s' % cl[st].filter_dict)
        sf = None
    else:
        for param in command_line.filter:
            try:
                st, param = map(str, param.split('.'))
            except:
                pass
            attr, value = map(str, param.split('='))
            cl[st].filter_dict[attr]=value
            log.debug('Filter setup for instance %s ' % st)
            st = command_line.type
    if not command_line.output:
        log.debug('Output format can be specified with the following parameters:\n %s' % cl[st].required_fields)
        so = [cl[st].required_fields[1]]
        log.debug('Using default query format: %s' % so)
    else:
        so = command_line.output
    res = cl[st].info(models)
    info_out = []
    for inst in res:
        for param in so:
            try:
                print param + ':\t' + str(inst.params_dict[param])
            except:
                log.debug("Parameter %s not available:" % param)


def fix_default_config():
    if not os.path.exists('/etc/abf/mock-urpm/configs/default.cfg'):
        if os.getuid() != 0:
            print "To set up a default configuration file, symbolic link in " +\
                    "/etc/abf/mock-urpm/configs have to be created. I need sudo rights to do it."
            exit(1)

        files = os.listdir('/etc/abf/mock-urpm/configs')
        print 'Avaliable configurations: '
        out = []
        for f in files:
            if not f.endswith('.cfg'):
                continue
            if f == 'site-defaults.cfg':
                continue
            out.append(f[:-4])

        print ', '.join(out)
        res = None
        while res not in out:
            if res is not None:
                print '"%s" is not a valid configuration.' % res
            res = raw_input('Select one (it will be remembered): ')
        os.symlink('/etc/abf/mock-urpm/configs/%s.cfg' % res, '/etc/abf/mock-urpm/configs/default.cfg')

def run_mock_urpm(binary=True):
    fix_default_config()
    if not command_line.config:
        command_line.config = 'default.cfg'
    if command_line.config.endswith('.cfg'):
        command_line.config = command_line.config[:-4]
    config_path = os.path.join(configs_dir, command_line.config + '.cfg')
    if not os.path.exists(config_path):
        log.error("Config file %s can not be found." % config_path)
        if os.path.basename(config_path) == 'default.cfg':
            log.error("You should create this file or a symbolic link to another config in order to execute 'abf mock-urpm' withow --config")
        exit(1)
    config_opts = {'plugins': [], 'scm_opts': {}}
    config_opts['plugin_conf'] = {'ccache_opts': {}, 'root_cache_opts': {}, 'bind_mount_opts': {'dirs': []}, 'tmpfs_opts': {}, 'selinux_opts': {}}
    try:
        execfile(config_path)
    except Exception, ex:
        log.error("Could not read the contents of '%s': %s" % (config_path, str(ex)))
        exit(2)

    basedir = ('basedir' in config_opts and config_opts['basedir']) or '/var/lib/abf/mock-urpm'
    root = config_opts['root']
    resultsdir = ('resultdir' in config_opts and config_opts['resultdir']) or '%s/%s/result' % (basedir, root)
    src_dir = basedir + '/src'

    if os.path.exists(src_dir):
        shutil.rmtree(src_dir)
    src = get_root_git_dir()
    if os.path.exists(os.path.join(src, '.abf.yml')):
        cmd = ['abf', 'fetch']
        if command_line.verbose:
            cmd.append('-v')
        execute_command(cmd, print_to_stdout=True, exit_on_error=True, cwd=src)
    shutil.copytree(src, src_dir, symlinks=True)

    spec_path = find_spec(src_dir)
    if not spec_path:
        log.error('Can not locate a spec file in %s' % src_dir)
        exit(1)
    spec_path = os.path.join(src_dir, spec_path)
    cmd = ['mock-urpm', '-r', command_line.config, '--buildsrpm', '--spec', spec_path, '--sources', src_dir, '--configdir', configs_dir ]
    if command_line.verbose:
        cmd.append('-v')
    log.info('Executing mock-urpm...')
    try:
        res = execute_command(cmd, print_to_stdout=True, exit_on_error=False, shell=False)
    except OSError, ex:
        log.error("Can not execute mock-urpm (%s). Maybe it is not installed?" % str(ex))
        exit(1)
    finally:
        shutil.rmtree(src_dir)

    srpm_path = glob(os.path.join(resultsdir, '*.src.rpm'))
    if len (srpm_path) != 1:
        log.error('Could not find a single src.rpm file in %s' % resultsdir)
        exit(1)
    srpm_path = srpm_path[0]
    srpm_path_new = os.path.join(os.getcwd(), os.path.basename(srpm_path))
    if os.path.exists(srpm_path_new):
        os.remove(srpm_path_new)
    shutil.move(srpm_path, os.getcwd())

    log.info('\nSRPM: %s\n' % srpm_path_new)
    if binary:
        cmd = ['mock-urpm', '-r', command_line.config, '--configdir', configs_dir,  srpm_path_new]
        if command_line.verbose:
            cmd.append('-v')
        log.info('Executing mock-urpm...')
        res = execute_command(cmd, print_to_stdout=True, exit_on_error=False, shell=False)
        os.remove(srpm_path)
        rpms = glob(os.path.join(resultsdir, '*.rpm'))
        print ''
        for rpm in rpms:
            new_path = os.path.join(os.getcwd(), os.path.basename(rpm))
            if os.path.exists(new_path):
                os.remove(new_path)
            shutil.move(rpm, os.getcwd())
            print('RPM: ' + os.path.join(os.getcwd(), os.path.basename(rpm)))

def localbuild_mock_urpm():
    # get project
    proj = get_project(models, must_exist=True)
    find_spec_problems()

    try:
        run_mock_urpm(binary=True)
    except OSError, ex:
        log.error(str(ex))
        exit(1)

def alias():
    log.debug('ALIAS started')
    if command_line.command == 'list':
        if not cfg['alias']:
            log.info('No aliases found')
            return
        for al_name in cfg['alias']:
            print '%10s: %s' % (al_name, cfg['alias'][al_name])
    elif command_line.command == 'add':
        if len(command_line.options) < 2:
            log.error('Not enough options. Use it like "abf alias add <alias_name> opt1 [opt2 ...]"')
            exit(1)
        al_name = command_line.options[0]
        if ' ' in al_name or '=' in al_name:
            log.error('Do not use " " or "=" for alias name!')
            exit(1)
        alias = ''
        for al in command_line.options[1:]:
            if ' ' in al:
                alias += '"%s" ' % al
            else:
                alias += al + ' '
        if al_name in cfg['alias']:
            log.warning('Alias "%s" already exists and will be overwritten.' % al_name)
        cfg['alias'][al_name] = alias
        log.info('Done')
    elif command_line.command == 'remove':
        if not command_line.options:
            log.error("Enter the alias name!")
            exit(1)
        al_name = command_line.options[0]
        if al_name not in cfg['alias']:
            log.error('Alias "%s" not found' % al_name)
            exit(1)
        cfg['alias'].pop(al_name)
        log.info('Done')



def localbuild_rpmbuild():
    log.debug('RPMBUILD started')
    src_dir = '/tmp/abf/rpmbuild'
    mkdirs('/tmp/abf')
    if os.path.exists(src_dir):
        shutil.rmtree(src_dir)
    src = get_root_git_dir()
    cmd = ['abf', 'fetch']
    if command_line.verbose:
        cmd.append('-v')
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    shutil.copytree(src, src_dir, symlinks=True)

    spec_path = find_spec(src_dir)
    if not spec_path:
        log.error('Can not locate a spec file in %s' % src_dir)
        exit(1)
    spec_path = os.path.join(src_dir, spec_path)
    cmd = ['rpmbuild', '-b'+command_line.build, '--define', '_topdir '+src_dir, '--define', '_sourcedir '+src_dir, spec_path]
    if command_line.verbose:
        cmd.append('-v')
    log.info('Executing rpmbuild...')
    try:
        res = execute_command(cmd, print_to_stdout=True, exit_on_error=False, shell=False)
    except OSError, ex:
        log.error("Can not execute rpmbuild (%s). Maybe it is not installed?" % str(ex))
        exit(1)
    log.info('Moving files to current directory...')
    items = [x for x in os.walk(src_dir+'/SRPMS')] + [x for x in os.walk(src_dir+'/RPMS')]
    for item in items:
        path, dirs, files = item
        for f in files:
            if not f.endswith('.rpm'):
                continue
            ff = os.path.join(path, f)
            new_ff = os.path.join(os.getcwd(), f)
            if os.path.exists(new_ff):
                os.remove(new_ff)
            shutil.move(ff, os.getcwd())
            if new_ff.endswith('.src.rpm'):
                log.info('SRPM: ' + new_ff)
            else:
                log.info('RPM: ' + new_ff)

    shutil.rmtree(src_dir)

def help():
    if command_line.command:
        sys.argv = [sys.argv[0], command_line.command, '-h']
    else:
        sys.argv = [sys.argv[0], '-h']
    parse_command_line()

def search():
    log.debug('SEARCH started')
    st = command_line.type
    sq = command_line.query
    cl = {'groups': Group, 'users': User, 'platforms': Platform, 'projects': Project}
    items = cl[st].search(models, sq)
    for item in items:
        print item

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


def split_repo_name(fullname):
    items = fullname.split('/')
    if len(items) == 2:
        repo_name = items[1]
        pl_name = items[0]
    elif len(items) == 1:
        repo_name = items[0]
        pl_name = default_build_platform
        log.info("Platform is assumed to be " + pl_name)
    else:
        log.error("repository argument format: [platform/]repository")
        exit(1)

    return [repo_name, pl_name]


def get_repo_id(repo_name, pl_name):
    # TODO: better to just get plaform by name...
    platforms = Platform.search(models, pl_name)
    for plat in platforms:
        if plat.name == pl_name:
            break

    for repo in plat.repositories:
        if repo.name == repo_name:
            break

    return repo.id


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

    if (not command_line.branch) and default_branch > '' and default_branch != 'master':
        os.chdir(project_name)
        check_branch = Popen(["git", "checkout", default_branch], stdout=PIPE, stderr=PIPE)
        (output, err) = check_branch.communicate()
        branch_missing = check_branch.wait()
        if branch_missing != 0:
            log.info("Branch " + default_branch + " is missing, will use HEAD")
        os.chdir("..")

    projects_cfg[proj]['location'] = os.path.join(os.getcwd(), project_name)

def put():
    log.debug('PUT started')

    path = get_root_git_dir()
    yaml_path = os.path.join(path, '.abf.yml')
    if not path:
        log.error("You have to be in a git repository directory")
        exit(1)
    _update_location()


    try:
        min_size = human2bytes(command_line.minimal_file_size)
    except ValueError, ex:
        log.error('Incorrect "--minimal-file-size" value: %s' % command_line.minimal_file_size)
        exit(1)
    error_count = upload_files(models, min_size, remove_files=not command_line.do_not_remove_files, path=path)
    if error_count:
        log.info('There were errors while uploading, stopping.')
        exit(1)

    if not command_line.message:
        return

    cmd = ['git', 'add', '--all']
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)

    if os.path.isfile(yaml_path):
        cmd = ['git', 'add', '-f', yaml_path]
        execute_command(cmd, print_to_stdout=True, exit_on_error=True)

    cmd = ['git', 'commit', '-m', command_line.message]
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)

    log.info('Commited.')
    cmd = ['git', 'push']
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    log.info('Pushed')

def fetch():
    log.debug('FETCH started')
    if command_line.filehash:
        log.info("Fetching file with hash " + command_line.filehash)
        os.system("wget -c --content-disposition " + file_store_url + "/api/v1/file_stores/" + command_line.filehash)
        exit(0)

    path = get_root_git_dir()
    if not path:
        log.error("You have to be in a git repository directory")
        exit(1)
    path = os.path.join(path, '.abf.yml')
    if not os.path.isfile(path):
        log.error('File "%s" can not be found' % path)
        exit(1)
    try:
        fetch_files(models, path, command_line.only)
    except yaml.scanner.ScannerError, ex:
        log.error('Invalid yml file %s!\nProblem in line %d column %d: %s' % (path, ex.problem_mark.line, ex.problem_mark.column, ex.problem))
    except yaml.composer.ComposerError, ex:
        log.error('Invalid yml file %s!\n%s' % (path, ex))

def store():
    log.debug('STORE started')
    p = os.path.expanduser(command_line.path)
    if not os.path.exists(p):
        log.error('File "%s" does not exist!' % p)
        exit(1)
    if not os.path.isfile(p):
        log.error('"%s" is not a regular file!' % p)
        exit(1)

    res = models.jsn.upload_file(p, silent=True)
    print res

def copy():
    log.debug('COPY started')
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

def pull_request():
    log.debug('PULL REQUEST started')

    proj = get_project(models, must_exist=True, name=command_line.project)

    PullRequest.new_pull_request(models, proj, command_line.title, command_line.body, command_line.to_ref, command_line.from_ref)

def fork_project():
    log.debug('FORK PROJECT started')

    source_proj = get_project(models, must_exist=True, name=command_line.source_project)

    if command_line.target_project:
        tmp = command_line.target_project.split('/')
        if len(tmp) > 2:
            log.error('Specify a project name as "group_name/project_name" or just "project_name"')
            exit(1)
        elif len(tmp) == 1:
            target_name = tmp[0]
            target_group = default_group
        elif len(tmp) == 2:
            target_group = tmp[0]
            target_name = tmp[1]
    else:
        target_group = default_group
        target_name = source_proj.name

    owner_group = Group.search(models, target_group)
    owner_user = User.search(models, target_group)

    if owner_group:
        owner_id = owner_group[0].id
    elif owner_user:
        # ABF doesn't seem to accept forks to platforms of other users
        print "No group named '" + target_group +"', will fork to you personal platform"
#        owner_id = owner_user[0].id
        owner_id = 0
    else:
        print "Incorrect target group"
        return 1

    ProjectCreator.fork_project(models, source_proj.id, owner_id, target_name)


def create():
    log.debug('CREATE PROJECT started')

    if not command_line.owner:
        command_line.owner = default_group

    owner_group = Group.search(models, command_line.owner)
    owner_user = User.search(models, command_line.owner)

    if owner_group:
        owner_id = owner_group[0].id
        owner_type = "Group"
    elif owner_user:
        owner_id = owner_user[0].id
        owner_type = "User"
    else:
        print "Incorrect owner data"
        return 1

    name = Popen('rpm -qp --qf="%{NAME}" ' + command_line.srpm, stdout=PIPE, shell=True).stdout.read()
    if name > '':
        description = Popen('rpm -qp --qf="%{SUMMARY}" ' + command_line.srpm, stdout=PIPE, shell=True).stdout.read()
        ProjectCreator.new_project(models, name, description, owner_id, owner_type)

        # Save cwd, create temp folder and go to it
        curdir = os.getcwd()
        tempdir = tempfile.mkdtemp()
        os.system("cp " + command_line.srpm + " " + tempdir)
        os.chdir(tempdir)

        # Get the newly created project and populate it with data from srpm
        os.system("abf get " + command_line.owner + "/" + name)
        os.chdir(tempdir + "/" + name)
        os.system("rpm2cpio ../" + os.path.basename(command_line.srpm) + " | cpio -id")
        os.system("abf put -m 'Imported from SRPM'")
        os.system("git push -u origin master")

        if command_line.branch:
            for branch in command_line.branch:
                os.system("git checkout -b " + branch);
                os.system("git push origin " + branch);
        elif (not command_line.no_def_branch) and default_branch > '' and default_branch != 'master':
            os.system("git checkout -b " + default_branch);
            os.system("git push origin " + default_branch);

        # Go back to initial dir and delete temp folder
        os.chdir(curdir)
        shutil.rmtree(tempdir)
    else:
        print "Failed to get information from SRPM"
        return 1

def add_project_to_repository():
    log.debug('ADD PROJECT TO REPO started')
    (repo_name, pl_name) = split_repo_name(command_line.repository)
    repo_id = get_repo_id(repo_name, pl_name)
    proj = get_project(models, must_exist=True, name=command_line.project)
    ProjectCreator.add_project_to_repo(models, repo_id, proj.id)

def remove_project_from_repository():
    log.debug('REMOVE PROJECT FROM REPO started')
    (repo_name, pl_name) = split_repo_name(command_line.repository)
    repo_id = get_repo_id(repo_name, pl_name)
    proj = get_project(models, must_exist=True, name=command_line.project)
    ProjectCreator.remove_project_from_repo(models, repo_id, proj.id)

def build():
    log.debug('BUILD started')

    if command_line.project and not (command_line.branch or command_line.tag or command_line.commit):
        log.error("You've specified a project name without branch, tag or commit (-b, -t or -c)")
        exit(1)

    tag_def = bool(command_line.tag)
    branch_def = bool(command_line.branch)
    commit_def = bool(command_line.commit)

    tmp = tag_def + branch_def + commit_def
    if tmp > 1:
        log.error("You should specify ONLY ONE of the following options: branch, tag or commit.")
        exit(1)

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


    # try to automatically resolve all the options, discarding all the other options except --branch
    # If we couldn't - use only user-given options. If we could, but user specified other parameters -
    #  reject averything we've resolved and use only user-given options.
    auto_resolved = True
    def auto_resolve():
        as_branch = None
        as_commit = None
        as_saveto = None
        if not command_line.project: # we are in a git repository and it is the project we are building
            as_branch = get_branch_name()
        if command_line.branch:
            as_branch = command_line.branch
        #log.debug('Auto resolved branch: ' + as_branch)
        if not as_branch:
            log.info('You\'ve specified a project without a branch.')
            return (None, None, None)

        for ref in proj.get_refs_list(models):
            if ref['ref'] == as_branch and ref['object']['type'] == 'commit':
                as_commit = ref['object']['sha']
                break
        if not as_commit:
            log.error("Could not resolve hash for branch '%s'" % (as_branch))
            return (None, None, None)

        for repo in proj.repositories:
            if repo.platform.name == as_branch or (as_branch == 'master' and repo.platform.name == 'cooker'):
                as_saveto = repo
        if not as_saveto:
            log.info('Could not resolve a platform to save to from the branch name "%s".' % as_branch)
            return (as_branch, as_commit, None)

        return (as_branch, as_commit, as_saveto)

    as_branch, as_commit, as_saveto  = auto_resolve()
    opts = 'Branch: %s, commit: %s, save-to-repo: %s' % (as_branch, as_commit, as_saveto)
    log.debug('A list of options which could be resolved automatically: %s' % opts)

    # get git commit hash

    commit_hash = None
    if tmp == 0:
        if as_commit: # use autoresolved commit hash
            commit_hash = as_commit
        else:
            log.error("Git branch, tag or commit can not be resolved automatically. Specify it by -b, -t or -c.")
            exit(1)
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
    if commit_hash != as_commit:
        as_saveto = None
        log.debug('Aitoresolved options were rejected.')
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
        pl_name = default_build_platform
        log.info("Save-to platform is assumed to be " + pl_name)
    elif len(items) == 0:
        if as_saveto and as_saveto in available_repos:
            pl_name = as_saveto.platform.name
            repo_name = as_saveto.name
        else:
            log.error("Save-to repository can not be resolved automatically. Specify it (-s).")
            exit(1)
    else:
        log.error("save-to-repository option format: [platform/]repository")
        exit(1)

    if (as_saveto and as_saveto in available_repos and as_saveto.platform.name == pl_name
                                                        and as_saveto.name == repo_name):
        save_to_repository = as_saveto
    else:
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
                log.debug("Platform for selected repository %s is assumed to be %s" % (repo_name, pl_name))
            else:
                log.error("'repository' option format: [platform/]repository")
                exit(1)

            if pl_name not in build_platform_names:
                log.error("Can not use build repositories from platform %s!\nSelect one of the following:\n%s" % (pl_name,
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
        build_repositories = []
        for repo in build_platform.repositories:
            if repo.name == 'main' or repo.name == save_to_repository.name:
                build_repositories.append(repo)
        log.info("Repositories to build with are assumed to be: " + str(build_repositories))

    if not build_repositories:
        log.error("You have to specify the repository(s) to build with (-r option)")
        exit(1)

    log.debug("Build repositories: " + str(build_repositories))

    # get architectures
    arches = []
    all_arches = Arch.get_arches(models)
    if command_line.arch:
        for arch in command_line.arch:
            a = Arch.get_arch_by_name(models, arch)
            if not a:
                log.error("Invalid architecture: %s" % arch)
                exit(1)
            arches.append(a)
    else:
        try_arches = ['i586','i686','x86_64']
        if str(build_repositories[0]).find("openmandriva") >= 0 or str(build_repositories[0]).find("cooker") >= 0:
            print "AAA" + str(build_repositories[0]);
            try_arches = ['i586','i686','x86_64','armv7hl','aarch64']

        for arch in try_arches:
            a = Arch.get_arch_by_name(models, arch)
            if a:
                arches.append(a)
        log.info("Arches are assumed to be " + str(arches))

    log.debug('Architectures: %s' % arches)

    auto_create_container = command_line.auto_create_container
    if auto_create_container is None:
        auto_create_container = True

    if command_line.auto_publish and not command_line.auto_publish_status:
        command_line.auto_publish_status = 'default'

    build_ids = BuildList.new_build_task(
        models,
        proj,
        save_to_repository,
        build_repositories,
        commit_hash,
        as_branch,
        command_line.update_type or BuildList.update_types[0],
        command_line.auto_publish_status or BuildList.auto_publish_statuses[0],
        arches,
        command_line.skip_personal,
        auto_create_container
    )
    ids = ','.join([str(i) for i in build_ids])
    projects_cfg['main']['last_build_ids'] = ids
    projects_cfg[str(proj)]['last_build_ids'] = ids

def publish():
    log.debug('PUBLISH started')
    for task_id in command_line.task_ids:
        try:
            bl = BuildList(models, task_id)
            if bl.status != 0:
                log.error("The status of build task %s is \"%s\", can not published!" % (bl.id, bl.status_string))
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
#        print '%-20s%s' %('Owner:', bl.owner.uname)
        print '%-20s%s' %('Project:', bl.project.fullname)
        print '%-20s%s' %('Status:', bl.status_string)
        print '%-20s%s' %('Build for platform:', bl.build_for_platform)
        print '%-20s%s' %('Save to repository:', bl.save_to_repository)
        print '%-20s%s' %('Build repositories:', bl.include_repos)
        print '%-20s%s' %('Extra repositories:', bl.extra_repositories)
        print '%-20s%s' %('Architecture:', bl.arch.name)
        print '%-20s%s' %('Created at:', bl.created_at)
        print '%-20s%s' %('Updated at:', bl.updated_at)
        print '%-20s%s' %('LOG Url:', bl.log_url)
        if bl.chroot_tree:
            print '%-20s%s' %('Chroot Tree:', bl.chroot_tree)
        print ''

def status():
    log.debug('STATUS started')
    ids = []
    if command_line.ID:
        ids = command_line.ID
    else:
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
        try:
            i = int(i)
        except:
            log.error('"%s" is not a number' % i)
            continue
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
    apply_aliases()
    parse_command_line()

    if command_line.verbose:
        Log.set_verbose()
    if command_line.quiet:
        Log.set_quiet()
    if command_line.clear_cache:
        Models.clear_cache()
    command_line.func()
