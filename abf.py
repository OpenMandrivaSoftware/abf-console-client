#!/usr/bin/python -tt
# -*- coding: UTF-8 -*-

import warnings
import importlib
warnings.filterwarnings('ignore','Module argparse was already imported')

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

import gettext
gettext.install('abf-console-client')

from abf.console.config import Config, mkdirs
from abf.console.log import Log
from abf.model import *


configs_dir = '/etc/abf/mock/configs/'

def test():
    log.debug(_('TEST started'))
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

    log.info(_('Datamodel seems to work fine'))


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

    parser = argparse.ArgumentParser(description=_('ABF Console Client'))
    parser.add_argument('-v', '--verbose', action='store_true', help=_('be verbose, display even debug messages'))
    parser.add_argument('-c', '--clear-cache', action='store_true', help=_('clear cached information about repositories, platforms, projects, etc.'))
    parser.add_argument('-q', '--quiet', action='store_true', help=_('Do not display info messages'))
    parser.add_argument('-C', '--config', action='store', help=_('config file to be used'))
    subparsers = parser.add_subparsers(title='command', dest='help')
    subparsers.required = True

    # help
    subparser = subparsers.add_parser('help', help=_('show a help for command'))
    subparser.add_argument('command', action='store', nargs='?', help=_('a command to show help for'))
    subparser.set_defaults(func=help)

    # alias
    subparser = subparsers.add_parser('alias', help=_('Manage aliases'))
    alias_commands = ['list', 'add', 'remove']
    subparser.add_argument('command', action='store', choices=alias_commands)
    subparser.add_argument('options', action='store', nargs='*', help=_('name and alias (not quoted, e. g. "abf alias add sg search groups") for adding, only name for removing.'))
    subparser.set_defaults(func=alias)

    # get
    subparser = subparsers.add_parser('get', help=_('clone a project from ABF'))
    subparser.add_argument('project', action='store', help=_('project name. ([group/]project). If no group specified, '
            'it\'s assumed to be your default group.'))
    subparser.add_argument('-b', '--branch', action='store', help=_('branch to checkout'))
    subparser.add_argument('--skip-proj-cfg-update', action='store_true', help=_('Do not update cache with information about project builds.'))
    subparser.set_defaults(func=get)

    # put
    subparser = subparsers.add_parser('put', help=_('Upload large binary files to File-Store and update (or create) .abf.yml file. Can also commit and push changes.'))
    subparser.add_argument('-m', '--message', action='store', help=_('With this option specified, "git add" for every file, "git commit -m MSG" and "git push" will be executed.'))
    subparser.add_argument('-f', '--add-folders', action='store_true', help=_('By default, the client does not add new folders to Git. This option will force it to add all new directories.'))
    subparser.add_argument('-b', '--add-binaries', action='store_true', help=_('By default, the client does not add new binary files to Git. This option will force it to add all new binaries (unless they are uploaded to file store - see below).'))
    subparser.add_argument('-s', '--minimal-file-size', default='0', action='store', help=_('The minimal file size to upload to File-Store. '
            'Default is 0B.'))
    subparser.add_argument('-n', '--do-not-remove-files', action='store_true', help=_('By default files are being removed on uploading. Override this behavior.'))
    subparser.add_argument('-a', '--upload-all', action='store_true', help=_('By default, console client analyzes spec file and tries to detect which files located in the '
										'current folder are really used by the project and uploads only these files to file store. '
										'With this option, console client will upload all binary files located in the current folder.'))
    subparser.set_defaults(func=put)

    # store
    subparser = subparsers.add_parser('store', help=_('Upload a given file to File-Store. Prints a sha1 hash or error message (with non-zero return code).'))
    subparser.add_argument('path', action='store', help=_('Path to file'))
    subparser.set_defaults(func=store)

    # update
    subparser = subparsers.add_parser('update', help=_('Update project settings.'))
    subparser.add_argument('-p', '--project', action='store',  help=_('Project to show information for (if needed). Format: '
        '"[group/]name". If no group specified, default group will be used.'))
    subparser.add_argument('--name', nargs='?', action='store', help=_('New project name.'))
    subparser.add_argument('--desc', nargs='?', action='store', help=_('Project description.'))
    subparser.add_argument('--visibility', nargs='?', action='store', help=_('Project visibility. Please specify "open" or "hidden".'))
    subparser.add_argument('--is_pkg', nargs='?', action='store', help=_('Is project a package. Please specify "true" or "false".'))
    subparser.add_argument('--maintainer', nargs='?', action='store', help=_('Project maintainer. You can specify either maintainer id or login.'))
    subparser.add_argument('--branch', nargs='?', action='store', help=_('Default branch for the project Git repository.'))
    subparser.add_argument('--issues', nargs='?', action='store', help=_('Should project issue tracker be enabled. Please specify "true" or "false".'))
    subparser.add_argument('--wiki', nargs='?', action='store', help=_('Should project wiki be enabled. Please specify "true" or "false".'))
    subparser.add_argument('--biarch', nargs='?', action='store', help=_('Enable/disable publishing 32bit packages into 64bit repository. Please specify "true" or "false".'))
    subparser.set_defaults(func=update)

    # fetch
    subparser = subparsers.add_parser('fetch', help=_('Download all the files listed in .abf.yml or file with given hash from File-Store to local directory.'))
    subparser.add_argument('filehash',  nargs='*', action='store', help=_('Download file with given hash'))
    subparser.add_argument('-o', '--only', action='append', help=_('Limit the list of downloaded files to this file name(s). This option can be specified more than once.'))
    subparser.set_defaults(func=fetch)

    # remote
    subparser = subparsers.add_parser('remote', help=_('Add remote Git repository and fetch it.'))
    subparser.add_argument('remote_group', action='store', help=_('ABF group to fetch from. This value will be also used as the name of remote repository.'))
    subparser.add_argument('remote_name', nargs='?', action='store', help=_('Project to fetch (by default the same project name is used as the current one).'))
    subparser.set_defaults(func=remote)

    # show
    subparser = subparsers.add_parser('show', help=_('show some general information. Bash autocomplete uses it.'))
    show_choices = ['buildlists', 'build-repos', 'build-platforms', 'save-to-repos', 'save-to-platforms']
    subparser.add_argument('type', action='store', nargs='?', choices=show_choices,help=_('The type of information to show'))
    subparser.add_argument('-p', '--project', action='store',  help=_('Project to show information for (if needed). Format: '
        '"[group/]name". If no group specified, default group will be used.'))
    subparser.set_defaults(func=show)

    # locate
    subparser = subparsers.add_parser('locate', help=_('tool can remember the project location and use it for some reasons (abfcd, etc.).'),
    epilog=_('Every interaction with git repository (build, get, put, etc.) updates the cached location of the project (overriding '
    'an existing one if needed). For any cached project you can execute "abfcd <project>" and you will cd to the project directory.'))
    locate_choices = ['update', 'update-recursive']
    subparser.add_argument('action', action='store', choices=locate_choices, nargs='?', help=_('The type of information to show'))
    subparser.add_argument('-p', '--project', action='store',  help=_('Project to show information for (if needed). Format: '
        '"[group/]name". If no group specified, default group will be used.'))
    subparser.add_argument('-d', '--directory', action='store',  help=_('Directory to update locations for. It should be a '
            'git repository for "update" and any directory for "update-recursive". If not specified - the current directory will be used'))
    subparser.set_defaults(func=locate)

    # build
    subparser = subparsers.add_parser('build', help=_('Initiate a build task on ABF.'), formatter_class=RawDescriptionHelpFormatter,
        epilog=_('NOTES:\n'
        'API takes git commit hash to build. So client have to resolve it.\n'
        '1) If you\'ve specified commit hash - it will be used "as is".\n'
        '2) If you\'ve specified branch or tag name - it will be resolved automatically\n'
        'using ABF API. (the hash of top commit will be used for branch)\n'
        '3) If you\'ve specified no git commit related options and you\'ve\n'
        ' specified a project name - this project\'s default branch will be used.\n'
        '4) If you\'ve specified no git commit related options and you\'ve\n'
        'not specified a project name (you have to be in a git repository) -\n'
        'the top remote commit of your current branch will be used.\n'))
    subparser.add_argument('-p', '--project', action='store', help=_('project name ([group/]project). If no group '
        'specified, it is assumed to be your default group. If the option is not specified and you are in a git '
        'repository directory - resolve a project name from it.'))
    subparser.add_argument('-b', '--branch', action='store', help=_('branch to build.'))
    subparser.add_argument('-t', '--tag', action='store', help=_('tag to build.'))
    subparser.add_argument('-c', '--commit', action='store', help=_('commit sha hash to build.'))
    subparser.add_argument('-s', '--save-to-repository', action='store', help=_('repository to save results to '
        '([platform/]repository). If no platform part specified, it is assumed to be "<default_group>_personal". '
        'If this option is not specified at all, "<default_group>_personal/main" will be used.'))
    subparser.add_argument('-a', '--arch', action='append', help=_('architectures to build, '
                        'can be set more than once. If not set - use all the available architectures.'))
    subparser.add_argument('-r', '--repository', action='append', help=_('repositories to build with ([platform/]repository). '
        'Can be set more than once. If no platform part specified, it is assumed to be your "<default_build_platform>".'
        ' If no repositories were specified at all, use the "main" repository from save-to platform.'))
    subparser.add_argument('-l', '--build-list', action='append', help=_('build list whose container should be used during the build. Can be specified more than once.'))
    subparser.add_argument('--auto-publish', action='store_true', help=_('deprecated synonym for --auto-publish-status=default.'))
    subparser.add_argument('--auto-publish-status', action='store', choices=BuildList.auto_publish_statuses, help=_('enable automatic publishing. Default is "%s".') %
                    (BuildList.auto_publish_statuses[0]))
    subparser.add_argument('--skip-personal', action='store_true', help=_('do not use personal repository to resolve dependencies.'))
    subparser.add_argument('--testing', action='store_true', help=_('Include "testing" subrepository.'))
    subparser.add_argument('--no-extra-tests', action='store_true', help=_('Do not launch comprehensive tests.'))
    subparser.add_argument('--auto-create-container', action='store_true', help=_('enable automatic creation of container'))
    subparser.add_argument('--no-cached-chroot', action='store_true', help=_('do NOT use cached chroot for the build'))
    subparser.add_argument('--save-chroot', action='store_true', help=_('save build chroot in case of failure'))
    subparser.add_argument('--update-type', action='store', choices=BuildList.update_types, help=_('Update type. Default is "%s".') %
                    (BuildList.update_types[0]) )
    subparser.add_argument('--external-nodes', action='store', choices=BuildList.external_nodes_vals, help=_('Use any external ABF node or own external ABF node. Default is "%s".') %
                    (BuildList.external_nodes_vals[0]) )
    subparser.add_argument('--skip-spec-check', action='store_true', help=_('Do not check spec file.'))
    subparser.add_argument('--skip-proj-cfg-update', action='store_true', help=_('Do not update cache with information about project builds.'))
    subparser.set_defaults(func=build)

    # chain-build
    subparser = subparsers.add_parser('chain_build', help=_('Initiate a chain of build tasks on ABF.'), formatter_class=RawDescriptionHelpFormatter)
    subparser.add_argument('project', nargs='*', action='store', help=_('Project name ([group/]project). If no group '
        'specified, it is assumed to be your default group. You can specify several projects to be built one after another. '
        'You can also group projects with ":" to indicate that they can be built in parallel. For example, '
        '"abf chain_build a b:c d" will build project "a", then (after "a" is built) will launch builds of "b" and "c" '
        'in parallel and after both of these projects are built, the build of "d" will be initiated. '
        'If automated publishing is set, then console client waits for every build to be published before starting the next build in the chain. '
        'If automated container creation is set, then console client waits for container to be ready and when the next build is started, containers '
        'from all previous builds are used as extra repositories.' ))
    subparser.add_argument('-i', '--infile', action='store', help=_('File with project names. You can omit project names in command line '
        'and provide a file with project names instead. The file will be read line by line. All projects specified at the same line '
        'will be built in parallel; the next line will be processed only after all the build from the previous line are completed successfully. '
        'Project name in a line can be separated by colon (":") or by space symbols.'))
    subparser.add_argument('-b', '--branch', action='store', help=_('branch to build.'))
    subparser.add_argument('-t', '--tag', action='store', help=_('tag to build.'))
    subparser.add_argument('-c', '--commit', action='store', help=_('commit sha hash to build.'))
    subparser.add_argument('-u', '--timeout', action='store', help=_('number of seconds to sleep between successive checks of build status.'))
    subparser.add_argument('-s', '--save-to-repository', action='store', help=_('repository to save results to '
        '([platform/]repository). If no platform part specified, it is assumed to be "<default_group>_personal". '
        'If this option is not specified at all, "<default_group>_personal/main" will be used.'))
    subparser.add_argument('-a', '--arch', action='append', help=_('architectures to build, '
                        'can be set more than once. If not set - use all the available architectures.'))
    subparser.add_argument('-r', '--repository', action='append', help=_('repositories to build with ([platform/]repository). '
        'Can be set more than once. If no platform part specified, it is assumed to be your "<default_build_platform>".'
        ' If no repositories were specified at all, use the "main" repository from save-to platform.'))
    subparser.add_argument('-l', '--build-list', action='append', help=_('build list whose container should be used during the build. Can be specified more than once.'))
    subparser.add_argument('--auto-publish', action='store_true', help=_('deprecated synonym for --auto-publish-status=default.'))
    subparser.add_argument('--auto-publish-status', action='store', choices=BuildList.auto_publish_statuses, help=_('enable automatic publishing. Default is "%s".') %
                    (BuildList.auto_publish_statuses[0]))
    subparser.add_argument('--skip-personal', action='store_true', help=_('do not use personal repository to resolve dependencies.'))
    subparser.add_argument('--testing', action='store_true', help=_('Include "testing" subrepository.'))
    subparser.add_argument('--no-extra-tests', action='store_true', help=_('Do not launch comprehensive tests.'))
    subparser.add_argument('--auto-create-container', action='store_true', help=_('enable automatic creation of container'))
    subparser.add_argument('--no-cached-chroot', action='store_true', help=_('do NOT use cached chroot for the build'))
    subparser.add_argument('--save-chroot', action='store_true', help=_('save build chroot in case of failure'))
    subparser.add_argument('--update-type', action='store', choices=BuildList.update_types, help=_('Update type. Default is "%s".') %
                    (BuildList.update_types[0]) )
    subparser.add_argument('--external-nodes', action='store', choices=BuildList.external_nodes_vals, help=_('Use any external ABF node or own external ABF node. Default is "%s".') %
                    (BuildList.external_nodes_vals[0]) )
    subparser.add_argument('--skip-proj-cfg-update', action='store_true', help=_('Do not update cache with information about project builds.'))
    subparser.set_defaults(func=chain_build)

    # mock
    subparser = subparsers.add_parser('mock', help=_('Build a project locally using mock.'), epilog=_('No checkouts will be made,'
                                                                    'the current git repository state will be used'))
    subparser.add_argument('-c', '--config', action='store', help=_('A config template to use. Specify one of the config names '
        'from %s. Directory path should be omitted. If no config specified, "default.cfg" will be used') % configs_dir)
    subparser.set_defaults(func=localbuild_mock_urpm)

    # rpmbuild
    subparser = subparsers.add_parser('rpmbuild', help=_('Build a project locally using rpmbuild.'), epilog=_('No checkouts will be made,'
                                                                    'the current git repository state will be used'))
    subparser.add_argument('-b', '--build', action='store', choices=['b', 's', 'a'], default='a', help=_('Build src.rpm (s), rpm (b) or both (a)'))
    subparser.add_argument('-s', '--save-rpmbuild-folder', action='store_true', help=_('Copy the whole rpmbuild folder into the current folder after the build'))
    subparser.set_defaults(func=localbuild_rpmbuild)

    # publish
    subparser = subparsers.add_parser('publish', help=_('Publish the task that have already been built.'))
    subparser.add_argument('task_ids', action='store', nargs="+", help=_('The IDs of tasks to publish.'))
    subparser.set_defaults(func=publish)

    # copy
    subparser = subparsers.add_parser('copy', help=_('Copy all the files from SRC_BRANCH to DST_BRANCH'))
    subparser.add_argument('src_branch', action='store', help=_('source branch'))
    subparser.add_argument('dst_branch', action='store', nargs='?', help=_('destination branch. If not specified, it\'s assumed to be the current branch'))
    subparser.add_argument('-p', '--pack', action='store_true', help=_('Create a tar.gz from the src_branch and put this archive and spec file to dst_branch'))
    subparser.set_defaults(func=copy)

    # pull request
    subparser = subparsers.add_parser('pullrequest', help=_('Send a pull request from SRC_BRANCH to DST_BRANCH'))
    subparser.add_argument('from_ref', action='store', help=_('source ref or branch'))
    subparser.add_argument('to_ref', action='store', help=_('destination ref or branch'))
    subparser.add_argument('title', action='store', help=_('Request title'))
    subparser.add_argument('body', action='store', help=_('Request body'))
    subparser.add_argument('-p', '--project', action='store', help=_('Source project name (group/project).'))
    subparser.add_argument('-d', '--dest', action='store', help=_('Destination project name (group/project). If not specified, the source project is used (this can be used to send requests from one project branch to another).'))
    subparser.set_defaults(func=pull_request)

    # fork project
    subparser = subparsers.add_parser('fork', help=_('Fork existing project'))
    subparser.add_argument('source_project', action='store', help=_('project to fork (group/project)'))
    subparser.add_argument('target_project', action='store', nargs='?', help=_('target project group and name (group/project)'))
    subparser.set_defaults(func=fork_project)

    # alias project
    subparser = subparsers.add_parser('proj_alias', help=_('Create alias of existing project'))
    subparser.add_argument('source_project', action='store', help=_('project to fork (group/project)'))
    subparser.add_argument('target_project', action='store', help=_('target project group and name (group/project)'))
    subparser.set_defaults(func=alias_project)

    # create empty project
    subparser = subparsers.add_parser('create_empty', help=_('Create empty project'))
    subparser.add_argument('name', action='store', help=_('project name'))
    subparser.add_argument('owner', action='store', nargs='?', help=_('who will own the project; default_owner is used by default'))
    subparser.add_argument('--description', action='store', help=_('project description'))
    subparser.add_argument('--visibility', action='store', choices=['public', 'private'], default='public', help=_('project visibility'))
    subparser.set_defaults(func=create_empty)

    # create project from SRPM
    subparser = subparsers.add_parser('create', help=_('Create project from SRPM'))
    subparser.add_argument('srpm', action='store', help=_('srpm file'))
    subparser.add_argument('owner', action='store', nargs='?', help=_('who will own the project; default_owner is used by default'))
    subparser.add_argument('-b', '--branch', action='append', help=_('create additional branch; can be set more than once.'))
    subparser.add_argument('--no-def-branch', action='store_true', help=_('Do not automatically create branch set as default in user config (if it is set to smth different from "master").'))
    subparser.set_defaults(func=create)

    # destroy project
    subparser = subparsers.add_parser('destroy', help=_('Destroy project'))
    subparser.add_argument('project', action='store', help=_('project name. ([group/]project). If no group specified, '
            'it\'s assumed to be your default group.'))
    subparser.set_defaults(func=destroy)

    # add project to repository
    subparser = subparsers.add_parser('add', help=_('Add project to specified repository'))
    subparser.add_argument('repository', action='store', help=_('target repository ([platform/]repository)'))
    subparser.add_argument('-p', '--project', action='store', help=_('project name (group/project).'))
    subparser.set_defaults(func=add_project_to_repository)

    # remove project from repository
    subparser = subparsers.add_parser('remove', help=_('Remove project from specified repository'))
    subparser.add_argument('repository', action='store', help=_('target repository ([platform/]repository)'))
    subparser.add_argument('-p', '--project', action='store', help=_('project name (group/project).'))
    subparser.set_defaults(func=remove_project_from_repository)

    # status
    subparser = subparsers.add_parser('status', help=_('get a build-task status'), epilog=_('If a project specified '
    ' or you are in a git repository - try to get the IDs from the last build task sent for this project. If you are not'
    ' in a git repository directory and project is not specified - try to get build IDs from the last build you\'ve done '
    'with console client.'))
    subparser.add_argument('ID', action='store', nargs='*', help=_('build list ID'))
    subparser.add_argument('-p', '--project', action='store',  help=_('Project. If last IDs for this project can be found - use them'))
    subparser.add_argument('-s', '--short', action='store_true',  help=_('Show one-line information including id, project, '
                                                                                                        'arch and status'))
    subparser.set_defaults(func=status)

    # clean
    subparser = subparsers.add_parser('clean', help=_('Analyze spec file and show missing and unnecessary files from '
                                                                            'the current git repository directory.'))
    subparser.add_argument('--auto-remove', action='store_true', help=_('automatically remove all the unnecessary files'))
    subparser.set_defaults(func=clean)

    # search
    subparser = subparsers.add_parser('search', help=_('Search for something on ABF.'), epilog=_('NOTE: only first 100 results of any request will be shown'))
    search_choices = ['users', 'groups', 'platforms', 'projects']
    subparser.add_argument('type', action='store', choices=search_choices, help=_('what to search for'))
    subparser.add_argument('query', action='store', help=_('a string to search for'))
    subparser.set_defaults(func=search)

    #list

    # info
    subparser = subparsers.add_parser('info', help=_('get information about single instance'))
    info_choices = ['platforms', 'repositories', 'projects']
    subparser.add_argument('type', action='store', choices=info_choices, help=_('type of the instance'))
    subparser.add_argument('-f', '--filter', action='store', help=_('The filter may be specified by defining multiple pairs <type>.<attribute>=<value> or <attribute>=<value>, where <type> is one of the following positional arguments: %s, <attribute> is the one of the instance fields or special attribute (page - using for pagination) and <value> - string, that can take asterisk (*) or anything else... Example: abf info projects -f platforms.name=rosa2012lts page=*') % info_choices, nargs='*')
    subparser.add_argument('-o', '--output', action='store', help=_('output format '), nargs='*')
    subparser.set_defaults(func=info_single)

    # test
    subparser = subparsers.add_parser('test', help=_('Execute a set of internal datamodel tests'))
    subparser.set_defaults(func=test)

    for s in subparsers._name_parser_map:
        subparsers._name_parser_map[s].add_argument('-v', '--verbose', action='store_true', help=_('be verbose, display even debug messages'))

    command_line = parser.parse_args(sys.argv[1:])


def info_single():
    st = command_line.type
    cl = {'platforms': Platform, 'repositories': Repository, 'projects': Project}
    if not command_line.filter:
        log.debug(_('Filter can be specified with the following parameters:\n %s' % cl[st].filter_dict))
        sf = None
    else:
        for param in command_line.filter:
            try:
                st, param = list(map(str, param.split('.')))
            except:
                pass
            attr, value = list(map(str, param.split('=')))
            cl[st].filter_dict[attr]=value
            log.debug(_('Filter setup for instance %s ') % st)
            st = command_line.type
    if not command_line.output:
        log.debug(_('Output format can be specified with the following parameters:\n %s') % cl[st].required_fields)
        so = [cl[st].required_fields[1]]
        log.debug(_('Using default query format: %s') % so)
    else:
        so = command_line.output
    res = cl[st].info(models)
    info_out = []
    for inst in res:
        for param in so:
            try:
                print(param + ':\t' + str(inst.params_dict[param]))
            except:
                log.debug(_("Parameter %s not available:") % param)


def fix_default_config():
    if not os.path.exists('/etc/abf/mock/configs/default.cfg'):
        if os.getuid() != 0:
            print((_("To set up a default configuration file, symbolic link in /etc/abf/mock/configs have to be created. I need sudo rights to do it.")))
            exit(1)

        files = os.listdir('/etc/abf/mock/configs')
        print((_('Avaliable configurations: ')))
        out = []
        for f in files:
            if not f.endswith('.cfg'):
                continue
            if f == 'site-defaults.cfg':
                continue
            out.append(f[:-4])

        print(', '.join(out))
        res = None
        while res not in out:
            if res is not None:
                print((_('"%s" is not a valid configuration.') % res))
            res = input(_('Select one (it will be remembered): '))
        os.symlink('/etc/abf/mock/configs/%s.cfg' % res, '/etc/abf/mock/configs/default.cfg')

def run_mock_urpm(binary=True):
    fix_default_config()
    if not command_line.config:
        command_line.config = 'default.cfg'
    if command_line.config.endswith('.cfg'):
        command_line.config = command_line.config[:-4]
    config_path = os.path.join(configs_dir, command_line.config + '.cfg')
    if not os.path.exists(config_path):
        log.error(_("Config file %s can not be found.") % config_path)
        if os.path.basename(config_path) == 'default.cfg':
            log.error(_("You should create this file or a symbolic link to another config in order to execute 'abf mock' without --config"))
        exit(1)
    config_opts = {'plugins': [], 'scm_opts': {}}
    config_opts['plugin_conf'] = {'ccache_opts': {}, 'root_cache_opts': {}, 'bind_mount_opts': {'dirs': []}, 'tmpfs_opts': {}, 'selinux_opts': {}}
    try:
        exec(compile(open(config_path).read(), config_path, 'exec'))
    except Exception as ex:
        log.error(_("Could not read the contents of '%(path)s': %(exception)s") % {'path': config_path, 'exception': str(ex)})
        exit(2)

    basedir = ('basedir' in config_opts and config_opts['basedir']) or '/var/lib/abf/mock'
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
        log.error(_('Can not locate a spec file in %s') % src_dir)
        exit(1)
    spec_path = os.path.join(src_dir, spec_path)
    cmd = ['mock', '-r', command_line.config, '--buildsrpm', '--spec', spec_path, '--sources', src_dir, '--configdir', configs_dir ]
    if command_line.verbose:
        cmd.append('-v')
    log.info(_('Executing mock...'))
    try:
        res = execute_command(cmd, print_to_stdout=True, exit_on_error=False, shell=False)
    except OSError as ex:
        log.error(_("Can not execute mock (%s). Maybe it is not installed?") % str(ex))
        exit(1)
    finally:
        shutil.rmtree(src_dir)

    srpm_path = glob(os.path.join(resultsdir, '*.src.rpm'))
    if len (srpm_path) != 1:
        log.error(_('Could not find a single src.rpm file in %s') % resultsdir)
        exit(1)
    srpm_path = srpm_path[0]
    srpm_path_new = os.path.join(os.getcwd(), os.path.basename(srpm_path))
    if os.path.exists(srpm_path_new):
        os.remove(srpm_path_new)
    shutil.move(srpm_path, os.getcwd())

    log.info(_('\nSRPM: %s\n') % srpm_path_new)
    if binary:
        cmd = ['mock', '-r', command_line.config, '--configdir', configs_dir,  srpm_path_new]
        if command_line.verbose:
            cmd.append('-v')
        log.info(_('Executing mock...'))
        res = execute_command(cmd, print_to_stdout=True, exit_on_error=False, shell=False)
        os.remove(srpm_path)
        rpms = glob(os.path.join(resultsdir, '*.rpm'))
        print('')
        for rpm in rpms:
            new_path = os.path.join(os.getcwd(), os.path.basename(rpm))
            if os.path.exists(new_path):
                os.remove(new_path)
            shutil.move(rpm, os.getcwd())
            print((_('RPM: ' + os.path.join(os.getcwd(), os.path.basename(rpm)))))

def localbuild_mock_urpm():
    # get project
    proj = get_project(models, must_exist=True)
    find_spec_problems()

    try:
        run_mock_urpm(binary=True)
    except OSError as ex:
        log.error(str(ex))
        exit(1)

def alias():
    log.debug('ALIAS started')
    if command_line.command == 'list':
        if not cfg['alias']:
            log.info(_('No aliases found'))
            return
        for al_name in cfg['alias']:
            print('%10s: %s' % (al_name, cfg['alias'][al_name]))
    elif command_line.command == 'add':
        if len(command_line.options) < 2:
            log.error(_('Not enough options. Use it like "abf alias add <alias_name> opt1 [opt2 ...]"'))
            exit(1)
        al_name = command_line.options[0]
        if ' ' in al_name or '=' in al_name:
            log.error(_('Do not use " " or "=" for alias name!'))
            exit(1)
        alias = ''
        for al in command_line.options[1:]:
            if ' ' in al:
                alias += '"%s" ' % al
            else:
                alias += al + ' '
        if al_name in cfg['alias']:
            log.warning(_('Alias "%s" already exists and will be overwritten.') % al_name)
        cfg['alias'][al_name] = alias
        log.info('Done')
    elif command_line.command == 'remove':
        if not command_line.options:
            log.error(_("Enter the alias name!"))
            exit(1)
        al_name = command_line.options[0]
        if al_name not in cfg['alias']:
            log.error(_('Alias "%s" not found') % al_name)
            exit(1)
        cfg['alias'].pop(al_name)
        log.info('Done')

def localbuild_rpmbuild():
    log.debug(_('RPMBUILD started'))
    src_dir = '/tmp/abf/rpmbuild'
    mkdirs('/tmp/abf')
    if os.path.exists(src_dir):
        shutil.rmtree(src_dir)
    src = get_root_git_dir()

    if os.path.isfile(".abf.yml"):
        cmd = ['abf', 'fetch']
        if command_line.verbose:
            cmd.append('-v')
        execute_command(cmd, print_to_stdout=True, exit_on_error=True)

    shutil.copytree(src, src_dir, symlinks=True)

    spec_path = find_spec(src_dir)
    if not spec_path:
        log.error(_('Can not locate a spec file in %s') % src_dir)
        exit(1)
    spec_path = os.path.join(src_dir, spec_path)
    cmd = ['rpmbuild', '-b'+command_line.build, '--define', '_topdir '+src_dir, '--define', '_sourcedir '+src_dir, spec_path]
    if command_line.verbose:
        cmd.append('-v')
    log.info(_('Executing rpmbuild...'))
    try:
        res = execute_command(cmd, print_to_stdout=True, exit_on_error=False, shell=False)
    except OSError as ex:
        log.error(_("Can not execute rpmbuild (%s). Maybe it is not installed?") % str(ex))
        exit(1)
    except ReturnCodeNotZero:
        log.info(_('Saving build folders to current directory...'))
        if os.path.exists(src + "/BUILD"):
            shutil.rmtree(src + "/BUILD")
        if os.path.exists(src + "/BUILDROOT"):
            shutil.rmtree(src + "/BUILDROOT")
        if os.path.exists(src_dir + "/BUILD"):
            shutil.copytree(src_dir + "/BUILD", src + "/BUILD", symlinks=True)
        if os.path.exists(src_dir + "/BUILDROOT"):
            shutil.copytree(src_dir + "/BUILDROOT", src + "/BUILDROOT", symlinks=True)

    log.info(_('Moving files to the current directory...'))

    if command_line.save_rpmbuild_folder:
        shutil.copytree(src_dir, src + "/rpmbuild", symlinks=True)
    else:
        for item in os.listdir(src_dir):
            if os.path.isfile(item) and not item.endswith('.spec') and item != ".abf.yml":
                log.info(_('SOURCE: ') + item)
                new_ff = os.path.join(os.getcwd(), item)
                if os.path.exists(new_ff):
                    os.remove(new_ff)
                shutil.move(src_dir + "/" + item, os.getcwd())

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
                    log.info(_('SRPM: ') + new_ff)
                else:
                    log.info(_('RPM: ') + new_ff)

    shutil.rmtree(src_dir)

def help():
    if command_line.command:
        sys.argv = [sys.argv[0], command_line.command, '-h']
    else:
        sys.argv = [sys.argv[0], '-h']
    parse_command_line()

def search():
    log.debug(_('SEARCH started'))
    st = command_line.type
    sq = command_line.query
    cl = {'groups': Group, 'users': User, 'platforms': Platform, 'projects': Project}
    items = cl[st].search(models, sq)
    for item in items:
        print(item)

def get_project_name_only(must_exist=True, name=None):
    if name:
        tmp = name.rstrip('/').split('/')
        if len(tmp) > 2:
            log.error(_('The project format is "[owner_name/]project_name"'))
            exit(1)
        elif len(tmp) == 1:
            project_name = tmp[0]
            log.info(_("The project group is assumed to be ") + default_group)
            owner_name = default_group
        else: # len == 2
            owner_name = tmp[0]
            project_name = tmp[1]
    else:
        owner_name, project_name = get_project_name()
        if not project_name:
            if must_exist:
                log.error(_('You are not in a git repository directory. Specify the project name please!'))
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
        log.error(_('The project %(owner)s/%(project)s does not exist!') % {'owner': owner_name, 'project': project_name})
        exit(1)
    except ForbiddenError:
        log.error(_('You do not have acces to the project %(owner)s/%(project)s!') % {'owner': owner_name, 'project': project_name})
        exit(1)

    log.debug(_('Project: %s') % proj)
    return proj

def get_maintainer_id(models, name):
    user_id = 0
    try:
        user_data = models.jsn.get_user_id(name)
        user_id = user_data['user']['id']
    except:
        log.error(_('Failed to get ID for user ') + name)
        exit(1)

    return user_id

def split_repo_name(fullname):
    items = fullname.rstrip('/').split('/')
    if len(items) == 2:
        repo_name = items[1]
        pl_name = items[0]
    elif len(items) == 1:
        repo_name = items[0]
        pl_name = default_build_platform
        log.info(_("Platform is assumed to be ") + pl_name)
    else:
        log.error(_("repository argument format: [platform/]repository"))
        exit(1)

    return [repo_name, pl_name]


def get_repo_id(repo_name, pl_name):
    # TODO: better to just get plaform by name...
    platforms = Platform.search(models, pl_name)
    plat_found = False
    for plat in platforms:
        if plat.name == pl_name:
            plat_found = True
            break

    if not plat_found:
        log.error(_("Platform %s doesn't exists!") % (pl_name))
        exit(1)

    repo_found = False
    for repo in plat.repositories:
        if repo.name == repo_name:
            repo_found = True
            break

    if not repo_found:
        log.error(_("Repository %s doesn't exists!") % (repo_name))
        exit(1)

    return repo.id


def get():
    log.debug(_('GET started'))
    proj = command_line.project
    tmp = proj.rstrip('/').split('/')
    if len(tmp) > 2:
        log.error(_('Specify a project name as "group_name/project_name" or just "project_name"'))
        exit(1)
    elif len(tmp) == 1:
        project_name = proj
        proj = '%s/%s' % (cfg['user']['default_group'], proj)
    elif len(tmp) == 2:
        project_name = tmp[1]

    uri = "%s/%s.git" % (cfg['user']['git_uri'], project_name)
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
            log.info(_("Branch " + default_branch + " is missing, will use HEAD"))
        os.chdir("..")

    if 'projects_cfg' in globals():
        projects_cfg[proj]['location'] = os.path.join(os.getcwd(), project_name)

def destroy():
    log.debug(_('DESTROY started'))

    proj = get_project(models, must_exist=True, name=command_line.project)

    ProjectCreator.destroy_project(models, proj.id)

def put():
    log.debug(_('PUT started'))

    path = get_root_git_dir()
    yaml_path = os.path.join(path, '.abf.yml')
    if not path:
        log.error(_("You have to be in a git repository directory"))
        exit(1)
    _update_location()


    try:
        min_size = human2bytes(command_line.minimal_file_size)
    except ValueError as ex:
        log.error(_('Incorrect "--minimal-file-size" value: %s') % command_line.minimal_file_size)
        exit(1)
    error_count = upload_files(models, min_size, remove_files=not command_line.do_not_remove_files, path=path, upload_all=command_line.upload_all)
    if error_count:
        log.info(_('There were errors while uploading, stopping.'))
        exit(1)

    if not command_line.message:
        return

    if not command_line.add_folders:
        files = [f for f in os.listdir('.') if os.path.isfile(f)]
        for f in files:
            if not is_text_file(f) and not command_line.add_binaries:
                continue
            cmd = ['git', 'add', f]
            execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    else:
        cmd = ['git', 'add', '--all']
        execute_command(cmd, print_to_stdout=True, exit_on_error=True)

    if os.path.isfile(yaml_path):
        cmd = ['git', 'add', '-f', yaml_path]
        execute_command(cmd, print_to_stdout=True, exit_on_error=True)

    cmd = ['git', 'commit', '-m', command_line.message]
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)

    log.info(_('Commited.'))
    cmd = ['git', 'push']
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    log.info(_('Pushed'))

def fetch():
    log.debug(_('FETCH started'))
    if command_line.filehash:
        for filehash in command_line.filehash:
            log.info(_("Fetching file with hash ") + filehash)
            os.system("wget -c --content-disposition " + file_store_url + "/api/v1/file_stores/" + filehash)
        exit(0)

    path = get_root_git_dir()
    if not path:
        log.error(_("You have to be in a git repository directory"))
        exit(1)
    path = os.path.join(path, '.abf.yml')
    if not os.path.isfile(path):
        log.error(_('File "%s" can not be found') % path)
        exit(1)
    try:
        fetch_files(models, path, command_line.only)
    except yaml.scanner.ScannerError as ex:
        log.error(_('Invalid yml file %(filename)s!\nProblem in line %(line)d column %(column)d: %(problem)s') % {'filename': path, 'line': ex.problem_mark.line, 'column': ex.problem_mark.column, 'problem': ex.problem})
    except yaml.composer.ComposerError as ex:
        log.error(_('Invalid yml file %(filename)s!\n%(exception)s') % {'filename': path, 'exception': ex})

def remote():
    log.debug(_('REMOTE started'))

    path = get_root_git_dir()
    if not path:
        log.error(_("You have to be in a git repository directory"))
        exit(1)
    owner_name, project_name = get_project_name()
    if project_name is None:
        log.error(_("Fail to detect project name"))
        exit(1)

    remote_group = command_line.remote_group
    if command_line.remote_name:
        project_name = command_line.remote_name

    uri = "%s/%s.git" % (cfg['user']['git_uri'], remote_group + "/" + project_name)
    cmd = ['git', 'remote', 'add', remote_group, uri]
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    cmd = ['git', 'fetch', remote_group]
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)

def store():
    log.debug(_('STORE started'))
    p = os.path.expanduser(command_line.path)
    if not os.path.exists(p):
        log.error(_('File "%s" does not exist!') % p)
        exit(1)
    if not os.path.isfile(p):
        log.error(_('"%s" is not a regular file!') % p)
        exit(1)

    res = models.jsn.upload_file(p, silent=True)
    print(res)

def copy():
    log.debug(_('COPY started'))
    sbrn = command_line.src_branch
    start_branch = get_branch_name()
    if not start_branch:
        log.error(_("You are not in a git directory"))
        exit(1)
    log.debug(_("Current branch is ") + start_branch)
    if command_line.dst_branch:
        dbrn = command_line.dst_branch
    else:
        dbrn = start_branch

    if sbrn == dbrn:
        log.error(_("Source and destination branches shold be different branches!"))
        exit(1)

    path = get_root_git_dir()
    log.debug(_("Repository root folder is ") + path)

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
    except Exception as ex:
        if type(ex) == ReturnCodeNotZero:
            log.error(str(ex))
        else:
            log.exception(ex)

        if stage == 1 or stage == 2:
            log.info(_("Checking out the initial branch (%s)") % start_branch)
            cmd = ['git', 'reset', '--hard', start_branch]
            execute_command(cmd, print_to_stdout=True, cwd=path)

    log.info('Done')

def pull_request():
    log.debug(_('PULL REQUEST started'))

    proj = get_project(models, must_exist=True, name=command_line.project)
    if command_line.dest:
        dest_proj = get_project(models, must_exist=True, name=command_line.dest)
    else:
        dest_proj = get_project(models, must_exist=True, name=command_line.project)

    PullRequest.new_pull_request(models, proj, dest_proj, command_line.title, command_line.body, command_line.to_ref, command_line.from_ref)

def fork_project():
    log.debug(_('FORK PROJECT started'))

    source_proj = get_project(models, must_exist=True, name=command_line.source_project)

    if command_line.target_project:
        tmp = get_project_name_only(True, command_line.target_project)
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
        print((_("No group named '%s', will fork to your personal platform") % target_group))
#        owner_id = owner_user[0].id
        owner_id = 0
    else:
        print((_("Incorrect target group")))
        return 1

    ProjectCreator.fork_project(models, source_proj.id, owner_id, target_name)

def alias_project():
    log.debug(_('ALIAS PROJECT started'))

    source_proj = get_project(models, must_exist=True, name=command_line.source_project)

    if command_line.target_project:
        tmp = get_project_name_only(True, command_line.target_project)
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
        print((_("No group named '%s', will create alias in your personal platform") % target_group))
#        owner_id = owner_user[0].id
        owner_id = 0
    else:
        print((_("Incorrect target group")))
        return 1

    ProjectCreator.alias_project(models, source_proj.id, owner_id, target_name)


def create_empty():
    log.debug(_('CREATE EMPTY PROJECT started'))

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
        print((_("Incorrect owner data")))
        return 1

    description = ""
    if command_line.description:
        description = command_line.description

    ProjectCreator.new_project(models, command_line.name, description, owner_id, owner_type, command_line.visibility)


def create():
    log.debug(_('CREATE PROJECT started'))

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
        print((_("Incorrect owner data")))
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
        os.system("abf put --upload-all -m 'Imported from SRPM'")
        os.system("git push -u origin master")

        if command_line.branch:
            for branch in command_line.branch:
                os.system("git checkout -b " + branch);
                os.system("git push origin " + branch);
        elif (not command_line.no_def_branch) and default_branch > '' and default_branch != 'master':
            os.system("git checkout -b " + default_branch);
            os.system("git push origin " + default_branch);

        # Supress output and errors for now, since only admins can set maintainers
        set_maintainer = Popen(['abf', 'update', '--maintainer', login], stdout=PIPE, stderr=PIPE)
        out, err = set_maintainer.communicate()
#        os.system("abf update --maintainer " + login)

        # Go back to initial dir and delete temp folder
        os.chdir(curdir)
        shutil.rmtree(tempdir)
    else:
        print((_("Failed to get information from SRPM")))
        return 1

def add_project_to_repository():
    log.debug(_('ADD PROJECT TO REPO started'))
    (repo_name, pl_name) = split_repo_name(command_line.repository)
    repo_id = get_repo_id(repo_name, pl_name)
    proj = get_project(models, must_exist=True, name=command_line.project)
    ProjectCreator.add_project_to_repo(models, repo_id, proj.id)

def remove_project_from_repository():
    log.debug(_('REMOVE PROJECT FROM REPO started'))
    (repo_name, pl_name) = split_repo_name(command_line.repository)
    repo_id = get_repo_id(repo_name, pl_name)
    proj = get_project(models, must_exist=True, name=command_line.project)
    ProjectCreator.remove_project_from_repo(models, repo_id, proj.id)

def chain_build():
    log.debug(_('CHAIN_BUILD started'))

    if command_line.timeout:
        timeout = command_line.timeout
    else:
        timeout = 60

    # Force printing of short status of the running builds
    command_line.short = True

    if not command_line.build_list:
        command_line.build_list = []

    if command_line.infile:
        if command_line.project:
            print((_("You can't specify '-i' option and project names in command line at the same time.")))
            exit(1)
        else:
            command_line.project = []
            f = open(command_line.infile, "r")
            # We allow project names in file to be separated not only by colons, but by spaces and mix of spaces around colons
            # Let's unify this and opnly leave colon as a separator
            regex_colon = re.compile(r"\s*:\s*")
            regex_spaces = re.compile(r"(\S)\s+(\S)")
            for line in f:
                line = regex_colon.sub(":", line)
                line = regex_spaces.sub(r"\1:\2", line)
                command_line.project.append(line.rstrip())

    for pr_set in command_line.project:
        build_ids = []
        if pr_set.find(":") < 0:
            log.debug(_('Launching build of %s') % pr_set)
            command_line.project = pr_set
            build_ids = build(return_ids=True)

        else:
            projects = pr_set.split(":")
            for p in projects:
                log.debug(_('Launching build of %s') % p)
                command_line.project = p
                new_build_ids = build(return_ids=True)
                build_ids.extend(new_build_ids)

        task_running = True
        success_builds = []

        while task_running:
            task_running = False
            for build_id in build_ids:
                if build_id in success_builds:
                    continue

                command_line.ID = [str(build_id)]
                stat = status(return_status=True)
                if stat[0][0] in ["build error", "publishing error", "publishing rejected", "build is canceling", "tests failed", "[testing] Publishing error", "unpermitted architecture"]:
                    print((_("One of the tasks failed, aborting chain build")))
                    exit(1)
                elif stat[0][0] in ["build pending", "rerun tests", "rerunning tests", "build started", "build is being published", "[testing] Build is being published'"]:
                    task_running = True
                elif stat[0][0] == "build complete":
                    if stat[0][1] == "container is being published":
                        task_running = True
                    elif stat[0][1] == "publishing error":
                        print((_("Container creation failed for build %d, aborting chain build") % build_id))
                        exit(1)
                    elif stat[0][1] == "waiting for request for publishing container":
                        print((_("WARNING: Build %d was not published and container was not created") % build_id))
                    else:
                        command_line.build_list.append(str(build_id))
                        success_builds.append(build_id)
                else:
                    success_builds.append(build_id)


            time.sleep(timeout)


def build(return_ids=False):
    log.debug(_('BUILD started'))

    if command_line.project and not (command_line.branch or command_line.tag or command_line.commit):
        log.error(_("You've specified a project name without branch, tag or commit (-b, -t or -c)"))
        exit(1)

    tag_def = bool(command_line.tag)
    branch_def = bool(command_line.branch)
    commit_def = bool(command_line.commit)

    tmp = tag_def + branch_def + commit_def
    if tmp > 1:
        log.error(_("You should specify ONLY ONE of the following options: branch, tag or commit."))
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
        log.error(_('The project %s is not a package and can not be built.') % proj)
        exit(1)


    # try to automatically resolve all the options, discarding all the other options except --branch
    # If we couldn't - use only user-given options. If we could, but user specified other parameters -
    #  reject averything we've resolved and use only user-given options.
    auto_resolved = True
    def auto_resolve():
        as_branch = None
        as_saveto = None
        if not command_line.project: # we are in a git repository and it is the project we are building
            as_branch = get_branch_name()
        if command_line.branch:
            as_branch = command_line.branch
        #log.debug('Auto resolved branch: ' + as_branch)
        if not as_branch:
            log.info(_('You\'ve specified a project without a branch.'))
            return (None, None)

        for repo in proj.repositories:
            if repo.platform.name == as_branch or (as_branch == 'master' and repo.platform.name == 'cooker') or (as_branch == 'rosa2014.1' and repo.platform.name == 'current'):
                as_saveto = repo
        if not as_saveto:
            log.info(_('Could not resolve a platform to save to from the branch name "%s".') % as_branch)
            return (as_branch, None)

        return (as_branch, as_saveto)

    as_branch, as_saveto  = auto_resolve()
    opts = 'Branch: %s, save-to-repo: %s' % (as_branch, as_saveto)
    log.debug(_('A list of options which could be resolved automatically: %s') % opts)

    # get git commit hash

    commit_hash = None
    if tmp == 0 and (not as_branch or not as_saveto):
        log.error(_("Git branch, tag or commit can not be resolved automatically. Specify it by -b, -t or -c."))
        exit(1)
    if tmp == 1:
        if commit_def:
            commit_hash = command_line.commit
    log.debug(_('Git commit hash: %s') % commit_hash)


    # get save-to repository
    save_to_repository = None
    build_for_platform = None

    available_repos = proj.repositories

    if command_line.save_to_repository:
        items = command_line.save_to_repository.rstrip('/').split('/')
    else:
        items = []
    if len(items) == 2:
        repo_name = items[1]
        pl_name = items[0]
    elif len(items) == 1:
        repo_name = items[0]
        pl_name = default_build_platform
        log.info(_("Save-to platform is assumed to be %s") % pl_name)
    elif len(items) == 0:
        if as_saveto and as_saveto in available_repos:
            pl_name = as_saveto.platform.name
            repo_name = as_saveto.name
        else:
            log.error(_("Save-to repository can not be resolved automatically. Specify it (-s)."))
            exit(1)
    else:
        log.error(_("save-to-repository option format: [platform/]repository"))
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
            log.error(_("Can not build for platform %(platform)s. Select one of the following:\n%(all_platforms)s") % {'platform': pl_name, 'all_platforms': ', '.join(pls)})
            exit(1)

        for repo in build_for_platform.repositories:
            if repo.name == repo_name:
                save_to_repository = repo
                break

        if not save_to_repository:
            log.error(_("Incorrect save-to repository %(platform)s/%(repo)s.\nSelect one of the following:\n%(all_repos)s") % {'platform': pl_name, 'repo': repo_name,
                    'all_repos': ', '.join([str(x) for x in build_for_platform.repositories])})
            exit(1)

    log.debug(_('Save-to repository: ') + str(save_to_repository))

    # get the list of build repositories
    build_platforms = Platform.get_build_platforms(models)
    build_platform_names = [x.name for x in build_platforms]
    build_repositories = []
    if command_line.repository:
        for repo in command_line.repository:
            items = repo.rstrip('/').split('/')
            if len(items) == 2:
                repo_name = items[1]
                pl_name = items[0]
            elif len(items) == 1:
                repo_name = items[0]
                pl_name = default_build_platform
                log.debug(_("Platform for selected repository %(repo)s is assumed to be %(plat)s") % {'repo': repo_name, 'plat': pl_name})
            else:
                log.error(_("'repository' option format: [platform/]repository"))
                exit(1)

            if pl_name not in build_platform_names:
                log.error(_("Can not use build repositories from platform %(platform)s!\nSelect one of the following:\n%(all_plats)s") % {'platform': pl_name,
                        'all_plats': ', '.join(build_platform_names)})
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
                log.error(_("Platform %(plat)s does not have repository %(repo)s!\nSelect one of the following:\n%(all_repos)s") % {'plat': pl_name, 'repo': repo_name,
                        'all_repos': ', '.join([x.name for x in build_platform.repositories])})
                exit(1)
            build_repositories.append(build_repo)
    else:
        build_platform = save_to_repository.platform

        if build_platform.name not in build_platform_names or not build_platform.repositories:
            log.error(_("Could not resolve repositories to build with. Please specify it (-r option)"))
            exit(1)
        build_repositories = []
        for repo in build_platform.repositories:
            if repo.name == 'main' or repo.name == save_to_repository.name:
                build_repositories.append(repo)
        log.info(_("Repositories to build with are assumed to be: ") + str(build_repositories))

    if not build_repositories:
        log.error(_("You have to specify the repository(s) to build with (-r option)"))
        exit(1)

    log.debug(_("Build repositories: ") + str(build_repositories))

    # get architectures
    arches = []
    all_arches = Arch.get_arches(models)
    if command_line.arch:
        for arch in command_line.arch:
            a = Arch.get_arch_by_name(models, arch)
            if not a:
                log.error(_("Invalid architecture: %s") % arch)
                exit(1)
            arches.append(a)
    else:
        try_arches = ['i586','i686','x86_64']
        if str(build_repositories[0]).find("openmandriva") >= 0 or str(build_repositories[0]).find("3.0") >= 0:
            try_arches = ['i586','x86_64','armv7hnl','aarch64']

        if str(build_repositories[0]).find("cooker") >= 0 or str(build_repositories[0]).find("4.0") >= 0:
            try_arches = ['i686','x86_64','armv7hnl','aarch64','znver1']

        for arch in try_arches:
            a = Arch.get_arch_by_name(models, arch)
            if a:
                arches.append(a)
        log.info(_("Arches are assumed to be ") + str(arches))

    log.debug(_('Architectures: %s') % arches)

    auto_create_container = command_line.auto_create_container
    if auto_create_container is None:
        auto_create_container = True

    if command_line.no_cached_chroot:
        cached_chroot = False
    else:
        cached_chroot = True

    if command_line.no_extra_tests:
        use_extra_tests = False
    else:
        use_extra_tests = True

    if not command_line.auto_publish and not command_line.auto_publish_status:
        command_line.auto_publish_status = default_publish_status

    if command_line.auto_publish and not command_line.auto_publish_status:
        command_line.auto_publish_status = 'default'

    extra_build_lists = []
    if command_line.build_list:
        for b in command_line.build_list:
            extra_build_lists.append(int(b))

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
        cached_chroot,
        command_line.save_chroot,
        auto_create_container,
        command_line.testing,
        use_extra_tests,
        extra_build_lists,
        # TODO: Read external_nodes config value from user's profile
        command_line.external_nodes or BuildList.external_nodes_vals[0]
    )
    ids = ','.join([str(i) for i in build_ids])
    if 'projects_cfg' in globals():
        projects_cfg['main']['last_build_ids'] = ids
        projects_cfg[str(proj)]['last_build_ids'] = ids

    if return_ids:
        return build_ids

def publish():
    log.debug('PUBLISH started')
    for task_id in command_line.task_ids:
        try:
            bl = BuildList(models, task_id)
            if bl.status != 0:
                log.error(_("The status of build task %(id)s is \"%(status)s\", can not published!") % {'id': bl.id, 'status': bl.status_string})
                continue
            res = bl.publish()
        except AbfApiException as ex:
            log.error(_('Could not publish task %(id)s: %(exception)s') % {'id': task_id, 'exception': str(ex)})


def _print_build_status(models, ID):
    try:
        bl = BuildList(models, ID)
    except AbfApiException as ex:
        log.error(_("Can not read buildlist %(id)s: %(exception)s") % {'id': ID, 'exception': ex})
        exit(3)
    if command_line.short:
        print(repr(bl))
    else:
        print('%-20s%s' %(_('Buildlist ID:'), bl.id))
        print('%-20s%s' %(_('Project:'), bl.project.fullname))
        print('%-20s%s' %(_('Status:'), bl.status_string))
        print('%-20s%s' %(_('Container path:'), bl.container_path))
        print('%-20s%s' %(_('Container status:'), bl.container_status_string))
        print('%-20s%s' %(_('Build for platform:'), bl.build_for_platform))
        print('%-20s%s' %(_('Save to repository:'), bl.save_to_repository))
        print('%-20s%s' %(_('Build repositories:'), bl.include_repos))
        print('%-20s%s' %(_('Extra repositories:'), bl.extra_repositories))
        print('%-20s%s' %(_('Architecture:'), bl.arch.name))
        print('%-20s%s' %(_('Created at:'), bl.created_at))
        print('%-20s%s' %(_('Updated at:'), bl.updated_at))
        print('%-20s%s' %(_('LOG Url:'), bl.log_url))
        if bl.chroot_tree:
            print('%-20s%s' %(_('Chroot Tree:'), bl.chroot_tree))
        print('')

    return [bl.status_string, bl.container_status_string]


def status(return_status=False):
    log.debug(_('STATUS started'))
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
                log.error(_("Can not find last build IDs. Specify a project name or ID"))
                exit(1)
            ids += projects_cfg['main']['last_build_ids'].split(',')
    ids = list(set(ids))
    stats = []
    for i in ids:
        try:
            i = int(i)
        except:
            log.error(_('"%s" is not a number') % i)
            continue
        stat = _print_build_status(models, i)
        stats.append(stat)

    if return_status:
        return stats


def _update_location(path=None, silent=True):
    try:
        if not path:
            path = os.getcwd()
        log.debug(_("Updating project location for %s") % path)
        group, name = get_project_name(path)
        if group:
            proj = '%s/%s' % (group, name)
            projects_cfg[proj]['location'] = path
            text = _("Project %(proj)s has been located in %(path)s") % {'proj': proj, 'path': path}
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
    log.debug(_('LOCATE started'))

    if not command_line.action: # show location
        if not command_line.project:
            print((_("To show a project location, you have to specify a project name ('-p' option)")))
            return

        tmp = command_line.project.rstrip('/').split('/')
        if len(tmp) > 2:
            log.error(_('error: the project format is "[owner_name/]project_name"'))
            exit(1)
        elif len(tmp) == 1:
            proj = '%s/%s' % (default_group, tmp[0])
        else: # len == 2
            proj = command_line.project

        if proj not in projects_cfg or 'location' not in projects_cfg[proj] or not projects_cfg[proj]['location']:
            print((_('error: project %s can not be located') % proj))
            exit(1)
        path = projects_cfg[proj]['location']
        if not os.path.isdir(path):
            print((_('error: project is not located in "%s" anymore') % path))
            projects_cfg[proj]['location'] = ''
            exit(1)
        print(path)
        return
    else:
        if command_line.action == 'update':
            path = command_line.directory or os.getcwd()
            _update_location(path)
        elif command_line.action == 'update-recursive':
            path = command_line.directory or os.getcwd()
            _update_location_recursive(path)

def get_true_false(value, key):
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    print((_("Please specify 'true' or 'false' for %s") % key))
    exit(1)

def update():
    log.debug(_('UPDATE started'))

    # get project
    proj = get_project(models, must_exist=True, name=command_line.project)

    if command_line.name is None:
        name = proj.name
    else:
        name = get_true_false(command_line.name, 'name')

    if command_line.desc is None:
        description = proj.description
    else:
        description = command_line.desc

    if command_line.visibility is None:
        visibility = proj.visibility
    else:
        visibility = command_line.visibility

    if command_line.is_pkg is None:
        is_package = proj.is_package
    else:
        is_package = get_true_false(command_line.is_pkg, 'is_pkg')

    if command_line.branch is None:
        default_branch = proj.default_branch
    else:
        default_branch = command_line.branch

    if command_line.issues is None:
        has_issues = proj.has_issues
    else:
        has_issues = get_true_false(command_line.issues, 'issues')

    if command_line.wiki is None:
        has_wiki = proj.has_wiki
    else:
        has_wiki = get_true_false(command_line.wiki, 'wiki')

    if command_line.maintainer is None:
        maintainer_id = proj.maintainer['id']
    else:
        maintainer_id = get_maintainer_id(models, command_line.maintainer)

    if command_line.biarch is None:
        publish_i686_into_x86_64 = proj.publish_i686_into_x86_64
    else:
        publish_i686_into_x86_64 = get_true_false(command_line.biarch, "biarch")

    Project.update(models, proj, name, description, visibility, is_package, default_branch,
                    has_issues, has_wiki, publish_i686_into_x86_64, maintainer_id)

def show():
    log.debug(_('SHOW started'))
    #Log.set_silent()
    t = command_line.type

    if t is None:
        proj = get_project(models, must_exist=True, name=command_line.project)
        for i in proj.required_fields:
             print((_("%s: %s") % (i, getattr(proj, i))))
    elif t == 'buildlists':
        proj = get_project(models, must_exist=True, name=command_line.project)
        res = models.jsn.get_project_buildlists(proj.id, '' ,1)
        for bl in res['build_lists']:
            buildlist = BuildList(models, bl['id'])
            print(buildlist)

    elif t in ['build-platforms', 'build-repos']:
        build_platforms = Platform.get_build_platforms(models)
        platform_names = []
        repo_names = []
        for plat in build_platforms:
            if plat.repositories:
                platform_names.append(plat.name)
            for repo in plat.repositories:
                repo_names.append(str(repo))
        out = (t == 'build-platforms' and platform_names) or (t == 'build-repos' and repo_names)
        print(' '.join(out))

    elif t in ['save-to-platforms', 'save-to-repos']:
        proj = get_project(models, must_exist=True, name=command_line.project)
        repos = proj.repositories
        platform_names = []
        repo_names = []
        for repo in repos:
            platform_names.append(repo.platform.name)
            repo_names.append(str(repo))
        platform_names = list(set(platform_names))
        out = (t == 'save-to-platforms' and platform_names) or (t == 'save-to-repos' and repo_names)
        print(' '.join(out))


def clean():
    log.debug(_("CLEAN started"))
    _update_location()
    find_spec_problems(auto_remove=command_line.auto_remove)


if __name__ == '__main__':
    global projects_cfg

    parse_command_line()

    if command_line.config:
        cfg = Config(conf_path=command_line.config)
        log = Log('abf', conf_path=command_line.config)
    else:
        cfg = Config()
        log = Log('abf')

    from abf.console.misc import *
    from abf.api.exceptions import *

    abf_url = cfg['main']['abf_url']
    file_store_url = cfg['main']['file_store_url']
    if cfg['main']['default_publish_status'] != '':
        if cfg['main']['default_publish_status'] in BuildList.auto_publish_statuses:
            default_publish_status = cfg['main']['default_publish_status']
        else:
            default_publish_status = BuildList.auto_publish_statuses[0]
            print((_("Incorrect value of 'default_publish_status' in config file, ignoring. Possible valus are: ") + "'" + str.join("', '", BuildList.auto_publish_statuses) + "'"))
    else:
        default_publish_status = BuildList.auto_publish_statuses[0]
        cfg['main']['default_publish_status'] = BuildList.auto_publish_statuses[0]

    login = cfg['user']['login']
    password = cfg['user']['password']
    default_group = cfg['user']['default_group']
    default_build_platform = cfg['user']['default_build_platform']
    default_branch = cfg['user']['default_branch']
    models_params = ((abf_url, file_store_url, login, password))

    models = Models(*models_params)

    apply_aliases()

    if not hasattr(command_line, "skip_proj_cfg_update"):
        command_line.skip_proj_cfg_update = False

    # These commands don't read or update projects file, so don't even read it
    # if one of these commands is launched
    commands_wo_cache = ['help','alias','put','store','fetch','show','mock','rpmbuild','publish','copy','pullrequest','fork','create','add','remove','search','info']
    if command_line.func.__name__ in commands_wo_cache:
        command_line.skip_proj_cfg_update = True

    if command_line.skip_proj_cfg_update is False:
        projects_cfg = Config(conf_path='~/.abf_projects', main_conf=False)

    if command_line.verbose:
        Log.set_verbose()
    if command_line.quiet:
        Log.set_quiet()
    if command_line.clear_cache:
        Models.clear_cache()
    command_line.func()
