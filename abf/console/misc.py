import os
import sys
import time
import select
import subprocess
import fcntl

from glob import glob
import shutil
import re
import yaml
import tempfile
import magic
import sha
import urllib2

from abf.console.log import Log
from abf.api.exceptions import *
log = Log('models')



class CommandTimeoutExpired(Exception):
    pass

class ReturnCodeNotZero(Exception):
    def __init__(self, message, code):
        super(ReturnCodeNotZero, self).__init__(message)
        self.code = code
        
def get_project_name(path=None):
    try:
        output, ret_code = execute_command(['git', 'remote', 'show', 'origin', '-n'], cwd=path)

        for line in output.split('\n'):
            if line.startswith('  Fetch URL:') and 'abf' in line:
                project_name = line.split('/')[-1][:-4]
                owner_name = line.split('/')[-2]
                return (owner_name, project_name)
        return (None, None)
    except ReturnCodeNotZero:
        return (None, None)
        
def get_project_name_version(spec_path):
    try:
        rpm = __import__('rpm') # it's initialization is too long to place it to the top of the file
        ts = rpm.TransactionSet()
        rpm_spec = ts.parseSpec(spec_path)
        name = rpm.expandMacro("%{name}")
        version = rpm.expandMacro("%{version}")
        return (name, version)
    except:
        return None
        
def get_project_data(spec_path):
        rpm = __import__('rpm') #  it's initialization is too long to place it to the top of the file
        ts = rpm.TransactionSet()
        rpm_spec = ts.parseSpec(spec_path)
        name = rpm.expandMacro("%{name}")
        version = rpm.expandMacro("%{version}")
        sources_all = rpm_spec.sources()
        
        sources = []
        patches = []
        for src in sources_all:
            name, number, flag = src
            if flag & 65536: # source file
                sources.append((name, number))
            elif flag & 131072:
                patches.append((name, number))
        return {'name': name, 'version': version, 'sources': sources, 'patches': patches}


def get_branch_name(path=None):
    try:
        output, ret_code = execute_command(['git', 'branch'], cwd=path)

        for line in output.split('\n'):
            if not line.startswith('*'):
                continue
            return line.split()[1]
    except ReturnCodeNotZero:
        return None
    
def get_current_commit_hash(path=None):
    try:
        output, ret_code = execute_command(['git', 'rev-parse', 'HEAD'], cwd=path)
        return output.strip()
    except ReturnCodeNotZero:
        return None
        
def get_remote_branch_hash(branch, cwd=None):
    ''' Get the hash of the remote branch top commit.
    If not in git repository directory - exception will be reised. If hash can not be found - return None'''
    re_ref = re.compile('^([0-9a-f]+) refs/remotes/\w+/%s$' % branch)
    
    output, ret_code = execute_command(['git', 'show-ref'], cwd=cwd)
    for line in output.split('\n'):
        res = re_ref.match(line)
        if res:
            h = res.group(1)
            return h
    return None
    
def get_tag_hash(tag, cwd=None):
    ''' Get the hash of the tag.
    If not in git repository directory - exception will be reised. If hash can not be found - return None'''
    re_ref = re.compile('^([0-9a-f]+) refs/tags/%s$' % tag)
    
    output, ret_code = execute_command(['git', 'show-ref', '--tags'], cwd=cwd)
    for line in output.split('\n'):
        res = re_ref.match(line)
        if res:
            h = res.group(1)
            return h
    return None   

def clone_git_repo_tmp(uri, depth=None):
    log.info('Cloning git repository (temporary workaround)')
    tmp_dir = tempfile.mkdtemp(prefix='tmp_abf_')
    log.info("Temporary directory os " + tmp_dir)
    cmd = ['git', 'clone', uri, tmp_dir]
    execute_command(cmd, print_to_stdout=True, exit_on_error=True)
    return tmp_dir
    
        
def get_root_git_dir(path=None):
    ''' Get the root directory of the git project '''
    if path:
        p = path
    else:
        p = os.getcwd()
        
    while '.git' not in os.listdir(p) or p == '/':
        p = os.path.dirname(p)
    if p == '/':
        return None
    else:
        return p
        
def get_spec_file(root_path):
    specs = glob(os.path.join(root_path, '*.spec'))
    log.debug("Spec files found: " + str(specs))
    if len(specs) == 1:
        spec = specs[0]
        return spec
    else:
        raise Excpetion("Could not find single spec file")

def find_spec(path=None):
    path = path or get_root_git_dir()
    if not path:
        log.error('No path specified and you are not in a git repository')
        exit(1)
    files = os.listdir(path)
    specs_present = []
    for fl in files:
        if fl.endswith('.spec'):
            specs_present.append(fl)
            
    if len(specs_present) == 0:
        raise Exception("No spec files found!")
    elif len(specs_present) > 1:
        raise Exception("There are more than one spec files found!")
    
    return specs_present[0]
        
def find_spec_problems(exit_on_error=True, strict=False, auto_remove=False):
    path = get_root_git_dir()
    files = os.listdir(path)
    
    files_present = []
    dirs_present = []
    yaml_files = []
    for fl in files:
        if fl.startswith('.'):
            continue
        if os.path.isdir(fl):
            dirs_present.append(fl)
            continue
        if fl.endswith('.spec'):
            continue
        files_present.append(fl)
        
    yaml_path = os.path.join(path, '.abf.yml')
    if os.path.isfile(yaml_path):
        with open(yaml_path, 'r') as fd:
            yaml_data = yaml.load(fd)
        if not 'sources' in yaml_data:
            log.error("Incorrect .abf.yml file: no 'sources' key")
            exit(1)
        for fl in yaml_data['sources']:
            yaml_files.append(fl)
            
    spec_path = find_spec(path)
    
    for d in dirs_present:
        log.info("warning: directory '%s' was found" % d)
        if auto_remove:
            shutil.rmtree(os.path.join(path,d) )
    
    res = get_project_data(spec_path)
    
    errors = False
    warnings = False
    files_required = []
    for fl in res['sources'] + res['patches']:
        fname, n = fl
        fname_base = os.path.basename(fname)
        
        files_required.append(fname_base)
        
        is_url = fname.startswith('http://')
        presents = fname_base in files_present
        in_yaml = fname_base in yaml_files
        
        if is_url  and in_yaml:
            warnings = True
            log.info('warning: file "%s" presents in spec (url) and in .abf.yml' % fname_base)
        
        if is_url and not presents:
            warnings = True
            log.info('warning: file "%s" is listed in spec as a URL, but does not present in the current directory or in .abf.yml file' % fname_base)
        
        if presents and in_yaml:
            warnings = True
            log.info('warning: file "%s" presents in the git directory and in .abf.yml' % fname_base)
            
        if not presents and not in_yaml and not is_url:
            errors = True
            log.info("error: missing file %s" % fname)
    
    remove_from_yaml = []
    for fl in set(files_present + yaml_files):
        if fl in files_required:
            continue # file have already been processed
        presents = fl in files_present
        in_yaml = fl in yaml_files
        if presents:
            warnings = True
            log.info('warning: unnecessary file "%s"' % fl)
            if auto_remove:
                os.remove( os.path.join(path, fl) )
        
        if in_yaml:
            warnings = True
            log.info('warning: unnecessary file "%s" in .abf.yml' % fl)
            remove_from_yaml.append(fl)
            
    if auto_remove:
        for fl in remove_from_yaml:
            yaml_data['sources'].pop(fl)
        with open(yaml_path, 'w') as fd:
            yaml.dump(yaml_data, fd, default_flow_style=False)
            log.info('.abf.yml file was rewritten')
    
    if exit_on_error and (errors or (strict and warnings)):
        exit(1)
        
def pack_project(root_path):
    # look for a spec file
    spec = get_spec_file(root_path)
        
    if spec:
        name, version = get_project_name_version(spec)
    else:
        log.error("Could not resolve project name and version from the spec file")
        return
    log.debug("Project name is " + str(name))
    log.debug("Project version is " + str(version))

    tardir = '%s-%s' % (name, version)
    tarball = tardir + ".tar.gz"
    log.debug("Writing %s/%s ..." % (root_path, tarball))
    
    full_tarball_path = '%s/%s' % (root_path, tarball)
    if os.path.exists(full_tarball_path):
        os.unlink(full_tarball_path)
    #open(full_tarball_path, 'w').close()
    cmd = ['tar', 'czf', full_tarball_path, '--exclude-vcs', os.path.basename(root_path)] 
    try:
        execute_command(cmd, cwd=os.path.dirname(root_path), exit_on_error=False)
    except ReturnCodeNotZero, ex:
        if ex.code != 1:
            raise
    
    #remove other files
    files = os.listdir(root_path)
    do_not_remove = ['.git', tarball, os.path.basename(spec)]
    log.debug("Removing files except " + str(do_not_remove))
    for f in files:
        if f in do_not_remove:
            continue
        f = os.path.join(root_path, f)
        log.debug('Removing ' + f)
        if os.path.isfile(f):
            os.remove(f)
        else:
            shutil.rmtree(f)
           

        
def execute_command(command, shell=False, cwd=None, timeout=0, raiseExc=True, print_to_stdout=False, exit_on_error=False):
    output = ""
    start = time.time()
    try:
        child = None
        log.debug("Executing command: %s" % command)
        child = subprocess.Popen(
            command,
            shell=shell,
            bufsize=0, close_fds=True,
            stdin=open("/dev/null", "r"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd
            )
        # use select() to poll for output so we dont block
        output = logOutput([child.stdout, child.stderr],
                start, timeout, print_to_stdout=print_to_stdout)
    except:
        # kill children if they arent done
        if child is not None and child.returncode is None:
            os.killpg(child.pid, 9)
        try:
            if child is not None:
                os.waitpid(child.pid, 0)
        except:
            pass
        raise
    
    # wait until child is done, kill it if it passes timeout
    niceExit=1
    while child.poll() is None:
        if (time.time() - start)>timeout and timeout!=0:
            niceExit=0
            os.killpg(child.pid, 15)
        if (time.time() - start)>(timeout+1) and timeout!=0:
            niceExit=0
            os.killpg(child.pid, 9)
    if not niceExit and raiseExc:
        raise CommandTimeoutExpired("Timeout(%s) expired for command:\n # %s\n%s" % (timeout, command, output))
    
    log.debug("Child returncode was: %s" % str(child.returncode))
    if child.returncode:
        if exit_on_error:
            exit(child.returncode)
        if raiseExc:
            raise ReturnCodeNotZero("Command failed.\nReturn code: %s\nOutput: %s" % (child.returncode, output), child.returncode)
        
    return (output, child.returncode)
    
def logOutput(fds, start=0, timeout=0, print_to_stdout=False):
    done = 0
    output = ''
    
    # set all fds to nonblocking
    for fd in fds:
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if not fd.closed:
            fcntl.fcntl(fd, fcntl.F_SETFL, flags| os.O_NONBLOCK)
       
    while not done:
        if (time.time() - start)>timeout and timeout!=0:
            done = 1
            break

        i_rdy,o_rdy,e_rdy = select.select(fds,[],[],1)
        for s in i_rdy:
            # slurp as much input as is ready
            string = s.read()
            if string == '':
                done = 1
                continue
            else:
                if print_to_stdout:
                    print string
            output += string
    return output
    
def is_text_file(path):
    m = magic.open(magic.MAGIC_MIME)
    m.load()
    r = m.file(path)
    log.debug("Magic type of file %s is %s" % (path, r))
    if r.startswith('text'):
        return True
    return False
    
def fetch_files(models, yaml_path, file_names=None):
    with open(yaml_path, 'r') as fd:
        yaml_data = yaml.load(fd)
    if not 'sources' in yaml_data:
        log.error("Incorrect .abf.yml file: no 'sources' key.")
        exit(1)
    yaml_files = yaml_data['sources']
    if file_names:
        to_fetch = dict([(x, yaml_files[x]) for x in file_names])
    else:
        to_fetch = yaml_files
    
    dest_dir = os.path.dirname(yaml_path)    
    for file_name in to_fetch:
        log.info('Fetching file %s' % file_name)
        path = os.path.join(dest_dir, file_name)
        if os.path.isfile(path):
            sha_hash_current = to_fetch[file_name]
            sha_hash_new = models.jsn.compute_sha1(path)
            if sha_hash_current == sha_hash_new:
                log.debug('The file %s already presents and has correct hash' % file_name)
                continue
            else:
                log.info('The file %s already presents but its hash is not the same as in .abf.yml, so it will be rewritten.' % file_name)
        try:
            models.jsn.fetch_file(to_fetch[file_name], path)
        except AbfApiException, ex:
            print 'error: ' + str(ex)

def upload_files(models, min_size, path=None, remove_files=True):
    log.debug('Uploading files for directory ' + str(path))
    spec_path = find_spec(path)
    dir_path = os.path.dirname(spec_path)
    errors_count = 0
    
    yaml_path = os.path.join(dir_path, '.abf.yml')
    yaml_file_changed = False
    yaml_files = {}
    yaml_data = {'sources':{}}
    if os.path.isfile(yaml_path):
        with open(yaml_path, 'r') as fd:
            yaml_data = yaml.load(fd)
        if not 'sources' in yaml_data:
            log.error("Incorrect .abf.yml file: no 'sources' key. The file will be rewritten.")
            yaml_file_changed = True
            yaml_data['sources'] = {}
        yaml_files = yaml_data['sources']
    
    sources = get_project_data(spec_path)['sources']
    for src, num in sources:
        is_url = False
        if '://' in src:
            src = os.path.basename(src)
            is_url = True
        
        do_not_upload = False
        source = os.path.join(dir_path, src)
        
        if not os.path.exists(source):
            if is_url:
                log.info('File %s not found, URL will be used instead. Skipping.' % src)
                continue
            if src not in yaml_files:
                log.error("error: Source%d file %s does not exist, skipping!" % (num, source))
                errors_count += 1;
            else:
                log.info('File %s not found, but it\'s listed in .abf.yml. Skipping.' % src)
            continue
        filesize = os.stat(source).st_size
        if filesize == 0:
            log.debug('Size of %s is 0, skipping' % src)
            do_not_upload = True
        if filesize < min_size:
            log.debug('Size of %s less then minimal, skipping' % src)
            do_not_upload = True
        if is_text_file(source):
            log.debug('File %s is textual, skipping' % src)
            do_not_upload = True
        if do_not_upload:
            # remove file from .abf.yml
            if src in yaml_files:
                yaml_files.pop(src)
                yaml_file_changed = True
            continue
        sha_hash = models.jsn.upload_file(source)
        
        if src not in yaml_files or sha_hash != yaml_files[src]:
            log.debug('Hash for file %s has been updated' % src)
            yaml_files[src] = sha_hash
            yaml_file_changed = True
        else:
            log.debug('Hash for file %s is already correct' % src)
        
        log.info('File %s has been processed' % src)
        if remove_files:
            log.debug('Removing file %s' % source)
            os.remove(source)
            
    if yaml_file_changed:
        log.debug('Writing the new .abf.yml file...')
        yaml_data['sources'] = yaml_files
        with open(yaml_path, 'w') as fd:
            yaml.dump(yaml_data, fd, default_flow_style=False)
            
    return errors_count

SYMBOLS = {
    'basic'     : ('b', 'k', 'm', 'g', 't'),
    'basic_long' : ('byte', 'kilo', 'mega', 'giga', 'tera'),
    'iec'           : ('bi', 'ki', 'mi', 'gi', 'ti'),
    'iec_long'       : ('byte', 'kibi', 'mebi', 'gibi', 'tebi'),
}


def human2bytes(s):
    if s.strip() == '0':
        return 0
    init = s
    num = ""
    while s and s[0:1].isdigit() or s[0:1] == '.':
        num += s[0]
        s = s[1:]
    num = float(num)
    letter = s.strip().lower()
    ss = None
    for name, sset in SYMBOLS.items():
        if letter in sset:
            ss = sset
            break
      
    if not ss:
        raise ValueError("can't interpret %r" % init)
    prefix = {ss[0]:1}

    for i, s in enumerate(sset[1:]):
        prefix[s] = 1 << (i+1)*10
    return int(num * prefix[letter])