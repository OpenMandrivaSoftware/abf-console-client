import os
import sys
import time
import select
import subprocess
import fcntl
import rpm
from glob import glob
import shutil

def mkdirs(path):
    ''' the equivalent of mkdir -p path'''
    if os.path.exists(path):
        return
    path = os.path.normpath(path)
    items = path.split('/')
    p = ''
    for item in items:
        p += '/' + item
        if not os.path.isdir(p):
            os.mkdir(p)
            
def ask_user(prompt, can_be_empty=False, variants=None):
    while True:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        res = sys.stdin.readline()
        res = res.strip()
        if not can_be_empty and not res:
            continue
        
        if variants:
            if res in variants:
                break
            else:
                continue
        break
        
    return res

class CommandTimeoutExpired(Exception):
    pass

class ReturnCodeNotZero(Exception):
    def __init__(self, message, code):
        super(ReturnCodeNotZero, self).__init__(message)
        self.code = code
        
def get_project_name():
    try:
        output = execute_command(['git', 'remote', 'show', 'origin', '-n'])

        for line in output.split('\n'):
            if line.startswith('  Fetch URL:'):
                project_name = line.split('/')[-1][:-4]
                owner_name = line.split('/')[-2]
                return (owner_name, project_name)
        return (None, None)
    except ReturnCodeNotZero:
        return (None, None)
        
def get_project_name_version(spec_path):
    try:
        ts = rpm.TransactionSet()
        rpm_spec = ts.parseSpec(spec_path)
        name = rpm.expandMacro("%{name}")
        version = rpm.expandMacro("%{version}")
        return (name, version)
    except:
        return None

def get_branch_name():
    try:
        output = execute_command(['git', 'branch'])

        for line in output.split('\n'):
            if not line.startswith('*'):
                continue
            return line.split()[1]
    except ReturnCodeNotZero:
        return None
        
def get_current_commit_hash():
    try:
        output = execute_command(['git', 'rev-parse', 'HEAD'])
        return output.strip()
    except ReturnCodeNotZero:
        return None
        
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
        
def pack_project(log, root_path):
    # look for a spec file
    specs = glob(os.path.join(root_path, '*.spec'))
    log.debug("Spec files found: " + str(specs))
    if len(specs) == 1:
        spec = specs[0]
    else:
        log.error("Could not find single spec file")
        return
        
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
        execute_command(cmd, log=log, cwd=os.path.dirname(root_path), exit_on_error=False)
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
           

        
def execute_command(command, log=None, shell=False, cwd=None, timeout=0, raiseExc=True, print_to_stdout=False, exit_on_error=False):
    output = ""
    start = time.time()
    try:
        child = None
        if log:
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
    
    if log:
        log.debug("Child returncode was: %s" % str(child.returncode))
    if child.returncode:
        if exit_on_error:
            exit(child.returncode)
        if raiseExc:
            raise ReturnCodeNotZero("Command failed.\nReturn code: %s\nOutput: %s" % (child.returncode, output), child.returncode)
        
    return output
    
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