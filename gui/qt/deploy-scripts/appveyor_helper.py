import os
import sys
import hashlib
import re
import subprocess
import time
import glob
import zipfile
import shutil
import requests
import json

# Timeout socket handling
import socket
import threading
import errno

from util import *

try:
    import zlib
    compression = zipfile.ZIP_DEFLATED
except:
    compression = zipfile.ZIP_STORED

modes = { zipfile.ZIP_DEFLATED: 'deflated',
          zipfile.ZIP_STORED:   'stored',
          }

try:
    # Python 3
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlparse
    from http.client import HTTPException
except ImportError:
    # Python 2
    from urllib2 import urlopen, Request, HTTPError, URLError
    from urlparse import urlparse
    from httplib import HTTPException

BINTRAY_SNAPSHOT_SERVER_PATH = "https://oss.jfrog.org/artifactory/oss-snapshot-local"
BINTRAY_RELEASE_SERVER_PATH = "https://oss.jfrog.org/artifactory/oss-release-local"
BINTRAY_MAVEN_GROUP_PATH = "/org/github/alberthdev/cemu/"
MAX_ATTEMPTS = 5
SHA256_STRICT = False

# Solution from Anppa @ StackOverflow
# http://stackoverflow.com/a/18468750/1094484
def timeout_http_body_read_to_file(response, fh, timeout = 60):
    def murha(resp):
        os.close(resp.fileno())
        resp.close()

    # set a timer to yank the carpet underneath the blocking read() by closing the os file descriptor
    t = threading.Timer(timeout, murha, (response,))
    
    t.start()
    fh.write(response.read())
    t.cancel()

def truncate_url(url):
    if len(url) > 70:
        truncated_url = url[:34] + ".." + url[len(url) - 34:]
    else:
        truncated_url = url
    
    return truncated_url

def check_file(path):
    try:
        test_fh = open(path)
        test_fh.close()
        return True
    except IOError:
        return False

# Note: suppress_errors will only work on HTTP errors
# Other errors will be forcefully displayed
def check_url(url, suppress_errors = True):
    check_attempts = 0
    found = False
    
    while check_attempts <= MAX_ATTEMPTS:
        # If we aren't on our first download attempt, wait a bit.
        if check_attempts > 0:
            print("         !! Download attempt failed, waiting 10s before retry...")
            print("            (attempt %i/%i)" % (check_attempts + 1, MAX_ATTEMPTS))
            
            # Wait...
            time.sleep(10)
        
        # Open the url
        try:
            f = urlopen(url)
            
            # Everything good!
            found = True
            break
            
        # Error handling...
        except HTTPError:
            if not suppress_errors:
                _, e, _ = sys.exc_info()
                print("         !! HTTP Error: %i (%s)" % (e.code, url))
                print("         !! Server said:")
                err = e.read().decode("utf-8")
                err = "         !! " + "\n         !! ".join(err.split("\n")).strip()
                print(err)
            
            found = False
            break
        except URLError:
            _, e, _ = sys.exc_info()
            print("         !! URL Error: %s (%s)" % (e.reason, url))
            
            found = False
            break
        except HTTPException:
            _, e, _ = sys.exc_info()
            print("         !! HTTP Exception: %s (%s)" % (str(e), url))
        except socket.error:
            _, e, _ = sys.exc_info()
            if e.errno == errno.EBADF:
                print("         !! Timeout reached: %s (%s)" % (str(e), url))
            else:
                print("         !! Socket Exception: %s (%s)" % (str(e), url))
        
        # Increment attempts
        check_attempts += 1
        
    if check_attempts > MAX_ATTEMPTS:
        print("         !! ERROR: URL check failed, assuming not found!")
    
    return found

def dlfile(url, dest = None):
    dl_attempts = 0
    dest = dest or os.path.basename(url)
    
    while dl_attempts <= MAX_ATTEMPTS:
        # If we aren't on our first download attempt, wait a bit.
        if dl_attempts > 0:
            print("         !! Download attempt failed, waiting 10s before retry...")
            print("            (attempt %i/%i)" % (dl_attempts + 1, MAX_ATTEMPTS))
            
            # Wait...
            time.sleep(10)
        
        # Open the url
        try:
            f = urlopen(url)
            print("         -> Downloading:")
            print("            %s" % truncate_url(url))

            # Open our local file for writing
            with open(dest, "wb") as local_file:
                timeout_http_body_read_to_file(f, local_file, timeout = 300)
                #local_file.write(f.read())
            
            # Everything good!
            break
            
        # Error handling...
        except HTTPError:
            _, e, _ = sys.exc_info()
            print("         !! HTTP Error: %i (%s)" % (e.code, url))
            print("         !! Server said:")
            err = e.read().decode("utf-8")
            err = "         !! " + "\n         !! ".join(err.split("\n")).strip()
            print(err)
        except URLError:
            _, e, _ = sys.exc_info()
            print("         !! URL Error: %s (%s)" % (e.reason, url))
        except HTTPException:
            _, e, _ = sys.exc_info()
            print("         !! HTTP Exception: %s (%s)" % (str(e), url))
        except socket.error:
            _, e, _ = sys.exc_info()
            if e.errno == errno.EBADF:
                print("         !! Timeout reached: %s (%s)" % (str(e), url))
            else:
                print("         !! Socket Exception: %s (%s)" % (str(e), url))
        
        # Increment attempts
        dl_attempts += 1
        
    if dl_attempts > MAX_ATTEMPTS:
        print("         !! ERROR: Download failed, exiting!")
        sys.exit(1)

def generate_file_md5(filename, blocksize=2**20):
    m = hashlib.md5()
    with open( filename , "rb" ) as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            m.update( buf )
    return m.hexdigest()

def generate_file_sha1(filename, blocksize=2**20):
    m = hashlib.sha1()
    with open( filename , "rb" ) as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            m.update( buf )
    return m.hexdigest()

def generate_file_sha256(filename, blocksize=2**20):
    m = hashlib.sha256()
    with open( filename , "rb" ) as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            m.update( buf )
    return m.hexdigest()

def output_md5(filename):
    md5_result = "%s  %s" % (filename, generate_file_md5(filename))
    print(md5_result)
    return md5_result

def output_sha1(filename):
    sha1_result = "%s  %s" % (filename, generate_file_sha1(filename))
    print(sha1_result)
    return sha1_result

def output_sha256(filename):
    sha256_result = "%s  %s" % (filename, generate_file_sha256(filename))
    print(sha256_result)
    return sha256_result

# True if valid, False otherwise
# Generalized validation function
#   filename    - file to check
#   chksum_file - checksum file to verify against
#   hash_name   - name of hash function used
#   hash_regex  - regex to validate the hash format
#   hash_func   - function to create hash from file
def validate_gen(filename, chksum_file, hash_name, hash_regex, hash_func):
    print("      -> Validating file with %s: %s" % (hash_name, filename))
    try:
        hash_fh = open(chksum_file)
        correct_hash = hash_fh.read().strip()
        hash_fh.close()
    except IOError:
        print("      !! ERROR: Could not open checksum file '%s' for opening!" % chksum_file)
        print("      !!        Exact error follows...")
        raise
    
    # Ensure hash is a valid checksum
    hash_match = re.match(hash_regex, correct_hash)

    if not hash_match:
        print("      !! ERROR: Invalid %s checksum!" % hash_name)
        print("      !!        Extracted %s (invalid): %s" % (hash_name, correct_hash))
        sys.exit(1)
    
    # One more thing - check to make sure the file exists!
    try:
        test_fh = open(filename, "rb")
        test_fh.close()
    except IOError:
        print("      !! ERROR: Can't check %s checksum - could not open file!" % hash_name)
        print("      !!        File: %s" % filename)
        print("      !! Traceback follows:")
        traceback.print_exc()
        return False
    
    # Alright, let's compute the checksum!
    cur_hash = hash_func(filename)
    
    # Check the checksum...
    if cur_hash != correct_hash:
        print("      !! ERROR: %s checksums do not match!" % hash_name)
        print("      !!        File: %s" % filename)
        print("      !!        Current %s: %s" % (hash_name, cur_hash))
        print("      !!        Correct %s: %s" % (hash_name, correct_hash))
        return False
    
    # Otherwise, everything is good!
    return True

def validate(filename):
    valid_md5 = validate_gen(filename, filename + ".md5", "MD5", r'^[0-9a-f]{32}$', generate_file_md5)
    
    if valid_md5:
        valid_sha1 = validate_gen(filename, filename + ".sha1", "SHA1", r'^[0-9a-f]{40}$', generate_file_sha1)
        
        if valid_sha1:
            # Special case: SHA256.
            # Check its existence before attempting to validate.
            if check_file(filename + ".sha256") or SHA256_STRICT:
                valid_sha256 = validate_gen(filename, filename + ".sha256", "SHA256", r'^[0-9a-f]{64}$', generate_file_sha256)
                
                return valid_sha256
            else:
                print("      !! **********************************************************")
                print("      !! WARNING: SHA256 checksum was not found for file:")
                print("         %s" % filename)
                print("         SHA256 checksum is strongly suggested for file integrity")
                print("         checking due to the weakness of other hashing algorithms.")
                print("         Continuing for now.")
                print("      !! **********************************************************")
                return True
        else:
            return False # alternatively, valid_sha1
    else:
        return False # alternatively, valid_md5

def dl_and_validate(url):
    validation_attempts = 0
    local_fn = os.path.basename(url)
    
    print("   -> Downloading + validating:")
    print("      %s" % truncate_url(url))
    
    # Download checksums...
    print("      -> Downloading checksums for file: %s" % (local_fn))
    dlfile(url + ".md5")
    dlfile(url + ".sha1")
    
    # SHA256 support was recently added, so do some careful checking
    # here.
    if check_url(url + ".sha256"):
        dlfile(url + ".sha256")
    else:
        # https://oss.jfrog.org/artifactory/oss-snapshot-local/org/github/alberthdev/cemu/appveyor-qt/Qt5.12.0_Rel_Static_Win32_DevDeploy.7z
        # https://oss.jfrog.org/api/storage/oss-snapshot-local/org/github/alberthdev/cemu/appveyor-qt/Qt5.12.0_Rel_Static_Win32_DevDeploy.7z
        url_parsed = urlparse(url)
        if url_parsed.netloc == "oss.jfrog.org" and url_parsed.path.startswith("/artifactory"):
            file_info_json_url = url.replace("://oss.jfrog.org/artifactory/", "://oss.jfrog.org/api/storage/")
            
            if check_url(file_info_json_url):
                dlfile(file_info_json_url, local_fn + ".info.json")
                
                file_info_json_fh = open(local_fn + ".info.json")
                file_info_json = json.loads(file_info_json_fh.read())
                file_info_json_fh.close()
                
                if "checksums" in file_info_json and "sha256" in file_info_json["checksums"]:
                    print("      -- Found SHA256 checksum from file JSON info.")
                    print("         SHA256: %s" % file_info_json["checksums"]["sha256"])
                    sha256_fh = open(local_fn + ".sha256", "w")
                    sha256_fh.write("%s" % file_info_json["checksums"]["sha256"])
                    sha256_fh.close()
                else:
                    print("      !! Could not find SHA256 checksum in JSON info.")
            else:
                print("      !! JSON info does not seem to work or exist:")
                print("         %s" % file_info_json_url)
                print("         Will not be able to locate SHA256 checksum.")
        else:
            print("      !! Could not detect a OSS JFrog URL. Will not be able")
            print("         to find SHA256 checksum.")
    
    while validation_attempts < MAX_ATTEMPTS:
        # If we aren't on our first download attempt, wait a bit.
        if validation_attempts > 0:
            print("      !! Download + validation attempt failed, waiting 10s before retry...")
            print("         (attempt %i/%i)" % (validation_attempts + 1, MAX_ATTEMPTS))
            # Wait...
            time.sleep(10)
        
        print("      -> Downloading file: %s" % (local_fn))
        
        # Download file...
        dlfile(url)
        
        # ...and attempt to validate it!
        if validate(local_fn):
            break
        
        # Validation failed... looping back around.
        # Increment validation attempt counter
        validation_attempts += 1
    
    if validation_attempts > MAX_ATTEMPTS:
        print("      !! ERROR: Download and validation failed, exiting!")
        sys.exit(1)
    
    print("      -> Downloaded + validated successfully:")
    print("         %s" % truncate_url(url))

def extract(filename):
    print("   -> Extracting file: %s" % filename)
    if not silent_exec(["7z", "x", "-y", "-oC:\\", filename]):
        print("   !! ERROR: Failed to extract file: " % filename)
        print("   !!        See above output for details.")
        sys.exit(1)

def install_deps():
    print(" * Attempting to download dependencies...")
    dl_and_validate('https://oss.jfrog.org/artifactory/oss-snapshot-local/org/github/alberthdev/cemu/appveyor-qt/Qt5.12.0_Rel_Static_Win32_DevDeploy.7z.001')
    dl_and_validate('https://oss.jfrog.org/artifactory/oss-snapshot-local/org/github/alberthdev/cemu/appveyor-qt/Qt5.12.0_Rel_Static_Win32_DevDeploy.7z.002')
    dl_and_validate('https://oss.jfrog.org/artifactory/oss-snapshot-local/org/github/alberthdev/cemu/appveyor-qt/Qt5.12.0_Rel_Static_Win64_DevDeploy.7z.001')
    dl_and_validate('https://oss.jfrog.org/artifactory/oss-snapshot-local/org/github/alberthdev/cemu/appveyor-qt/Qt5.12.0_Rel_Static_Win64_DevDeploy.7z.002')
    
    print(" * Attempting to install dependencies...")
    extract('Qt5.12.0_Rel_Static_Win32_DevDeploy.7z.001')
    extract('Qt5.12.0_Rel_Static_Win64_DevDeploy.7z.001')
    
    print(" * Successfully installed build dependencies!")

def overwrite_copy(src, dest):
    src_bn = os.path.basename(src)
    dest_path = os.path.join(dest, src_bn)
    
    src_fh = open(src, "rb")
    dest_fh = open(dest_path, "wb")
    
    dest_fh.write(src_fh.read())
    
    src_fh.close()
    dest_fh.close()

def collect_static_main_files(arch, build_path, dest, extra_wc = None):
    file_list = []
    
    if extra_wc:
        for copy_type in extra_wc:
            print("   -> Copying %s files (%s)..." % (copy_type, arch))
            copy_wc = extra_wc[copy_type]
            
            for file in glob.glob(copy_wc):
                print("      -> Copying %s (%s, %s)..." % (os.path.basename(file), arch, copy_type))
                overwrite_copy(file, dest)
        
    
    # Finally, add our binary!
    print("   -> Copying main executable (%s)..." % (arch))
    exec_path = os.path.join(build_path, "CEmu.exe")
    overwrite_copy(exec_path, dest)
    
    # No manifest needed - already embedded into exe.

# wc = wildcard
# extra_wc: dictionary of extra wildcard paths to copy in!
#   example: { "More DLLs" : "C:\MoreDLLs\*.dll"}
def collect_main_files(arch, vcredist_wc_path, ucrt_wc_path, build_path, dest, extra_wc = None):
    file_list = []
    
    print("   -> Searching VCRedist for DLL files to include (%s)..." % (arch))
    
    for file in glob.glob(vcredist_wc_path):
        print("   -> Copying %s (%s, VCRedist)..." % (os.path.basename(file), arch))
        overwrite_copy(file, dest)
    
    for file in glob.glob(ucrt_wc_path):
        print("   -> Copying %s (%s, UCRT)..." % (os.path.basename(file), arch))
        overwrite_copy(file, dest)
    
    if extra_wc:
        for copy_type in extra_wc:
            print("   -> Copying %s files (%s)..." % (copy_type, arch))
            copy_wc = extra_wc[copy_type]
            
            for file in glob.glob(copy_wc):
                print("      -> Copying %s (%s, %s)..." % (os.path.basename(file), arch, copy_type))
                overwrite_copy(file, dest)
        
    
    # Finally, add our binary!
    print("   -> Copying main executable (%s)..." % (arch))
    exec_path = os.path.join(build_path, "CEmu.exe")
    overwrite_copy(exec_path, dest)
    
    # No manifest needed - already embedded into exe.

def collect_qt_files_with_qml(arch, deploy_tool, dest, exe_file, qmldir = "qml"):
    os.environ.pop("VCINSTALLDIR", None)
    print("   -> Collecting all Qt dependencies (%s)..." % (arch))
    if not simple_exec([deploy_tool, "--qmldir", qmldir, "--dir", dest, exe_file]):
        print("   !! ERROR: Failed to collect Qt dependencies!")
        print("   !!        See above output for details.")
        sys.exit(1)

def collect_qt_files(arch, deploy_tool, dest, exe_file):
    os.environ.pop("VCINSTALLDIR", None)
    print("   -> Collecting all Qt dependencies (%s)..." % (arch))
    if not simple_exec([deploy_tool, "--no-angle", "--no-opengl-sw", "--no-system-d3d-compiler", "--dir", dest, exe_file]):
        print("   !! ERROR: Failed to collect Qt dependencies!")
        print("   !!        See above output for details.")
        sys.exit(1)

def build_file_list(arch, dest):
    file_list = []
    root_parts = len(dest.split(os.sep))
    
    print("   -> Finalizing file list for release (%s)..." % (arch))
    
    for root, dirnames, filenames in os.walk(dest):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            # Delete root folder from path to form archive path!
            arc_path = os.sep.join(full_path.split(os.sep)[root_parts:])
            file_list.append([full_path, arc_path])
    
    return file_list

def make_zip(arch, filename, file_list):
    print(" * Building ZIP file %s (%s)..." % (filename, arch))
    
    if compression == zipfile.ZIP_DEFLATED:
        print("   (Compression is enabled!)")
    else:
        print("   (Compression is DISABLED!)")
    
    zf = zipfile.ZipFile(filename, mode='w')
    try:
        for file_entry in file_list:
            if len(file_entry) == 1:
                full_path = file_entry[0]
                arc_path = full_path
            elif len(file_entry) == 2:
                full_path = file_entry[0]
                arc_path = file_entry[1]
            else:
                print("   !! ERROR: Bug - invalid number of file elements in file_entry!")
                print("             file_entry is %s" % (str(file_entry)))
                sys.exit(1)
            
            print("   -> Adding %s -> %s..." % (full_path, arc_path))
            zf.write(full_path, compress_type=compression, arcname=arc_path)
    finally:
        print("   -> Closing ZIP file %s (%s)..." % (filename, arch))
        zf.close()
    
    print(" * Successfully built ZIP file %s (%s)!" % (filename, arch))

def upload_snapshot(filename, cur_timestamp, snap_base_fn, bintray_api_username, bintray_api_key, extra_path = None):
    cur_date = cur_timestamp.split("_")[0]
    cur_date_ym = cur_date[:6]
    
    full_path = BINTRAY_SNAPSHOT_SERVER_PATH + BINTRAY_MAVEN_GROUP_PATH + "git/" + cur_date_ym + "/" + cur_date + "/" + snap_base_fn + "/"
    
    base_fn = os.path.basename(filename)
    
    print(" * Preparing to deploy snapshot: %s" % base_fn)
    
    if extra_path:
        full_path += extra_path
    
    # Compute MD5, SHA1, and SHA256
    print("   -> Computing checksums before uploading...")
    file_md5sum = generate_file_md5(filename)
    file_sha1sum = generate_file_sha1(filename)
    file_sha256sum = generate_file_sha256(filename)
    
    print("   -> MD5    = %s" % file_md5sum)
    print("   -> SHA1   = %s" % file_sha1sum)
    print("   -> SHA256 = %s" % file_sha256sum)
    
    headers = {
                'X-Checksum-Md5'    : file_md5sum,
                'X-Checksum-Sha1'   : file_sha1sum,
                'X-Checksum-Sha256' : file_sha256sum,
              }
    
    #files = {base_fn: open(filename, 'rb')}
    fh = open(filename, 'rb')
    file_data = fh.read()
    fh.close()
    
    print(" * Uploading/deploying snapshot: %s" % base_fn)
    r = requests.put(full_path + base_fn, headers = headers, data = file_data, \
                    auth = (bintray_api_username, bintray_api_key))
    
    print(" * Resulting status code: %i" % r.status_code)
    print(" * Resulting response:\n%s" % r.content)
    
    if r.status_code != 201:
        print(" ! ERROR: Upload/deployment of snapshot failed!")

def deploy_snapshots():
    print(" * Preparing to deploy...")
    
    # Check for our needed environment variables!
    # First up? Bintray!
    bintray_api_username = os.environ.get("BINTRAY_API_USERNAME")
    bintray_api_key = os.environ.get("BINTRAY_API_KEY")
    
    if (bintray_api_username == None) or (bintray_api_key == None):
        print(" ! ERROR: Authentication environmental variables not found!")
        print(" !        BINTRAY_API_USERNAME defined? %s" % ("Yes" if bintray_api_username else "No"))
        print(" !        BINTRAY_API_KEY defined?      %s" % ("Yes" if bintray_api_key else "No"))
        sys.exit(1)
    
    # One more - are the Qt5 dynamic directories defined?
    qt5_bin_dir_dynamic_32 = os.environ.get("QT5_BIN_DIR_DYNAMIC_32")
    qt5_bin_dir_dynamic_64 = os.environ.get("QT5_BIN_DIR_DYNAMIC_64")
    
    if (qt5_bin_dir_dynamic_32 == None) or (qt5_bin_dir_dynamic_64 == None):
        print(" ! ERROR: Qt5 dynamic location environmental variables not found!")
        print(" !        QT5_BIN_DIR_DYNAMIC_32 defined? %s" % ("Yes" if QT5_BIN_DIR_DYNAMIC_32 else "No"))
        print(" !        QT5_BIN_DIR_DYNAMIC_64 defined? %s" % ("Yes" if QT5_BIN_DIR_DYNAMIC_64 else "No"))
        sys.exit(1)
    
    # Make a directory for our deploy ZIPs
    mkdir_p("deploy")
    mkdir_p(os.path.join("deploy", "release32"))
    mkdir_p(os.path.join("deploy", "release64"))
    mkdir_p(os.path.join("deploy", "release32_debug"))
    mkdir_p(os.path.join("deploy", "release64_debug"))
    
    mkdir_p(os.path.join("deploy_static", "release32"))
    mkdir_p(os.path.join("deploy_static", "release64"))
    mkdir_p(os.path.join("deploy_static", "release32_debug"))
    mkdir_p(os.path.join("deploy_static", "release64_debug"))
    
    # git rev-parse --short HEAD
    git_rev = output_exec(["git", "rev-parse", "--short", "HEAD"])
    
    if git_rev == None:
        sys.exit(1)
    
    git_rev = git_rev.decode("utf-8").strip()
    
    # Snapshot filename - based on http://zeranoe1.rssing.com/chan-5973786/latest.php
    cur_timestamp = time.strftime("%Y%m%d_%H%M%S")
    snap_base_fn = "cemu-%s-git-%s" % (cur_timestamp, git_rev)
    snap_base_path = os.path.join("deploy", snap_base_fn)
    
    # Locate files that we need!
    print(" * Collecting all dependencies for deployment...")
    
    collect_main_files("x86", r"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\redist\x86\Microsoft.VC140.CRT\*.dll",
                       r"C:\Program Files (x86)\Windows Kits\10\Redist\ucrt\DLLs\x86\*.dll",
                       os.path.join("build_32", "release"),
                       os.path.join("deploy", "release32"),
                       extra_wc = {
                                    "vcpkg provided DLLs" : os.path.join("build_32", "release") + r"\*.dll"
                                  }
                      )
    collect_main_files("x64", r"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\redist\x64\Microsoft.VC140.CRT\*.dll",
                       r"C:\Program Files (x86)\Windows Kits\10\Redist\ucrt\DLLs\x64\*.dll",
                       os.path.join("build_64", "release"),
                       os.path.join("deploy", "release64"),
                       extra_wc = {
                                    "vcpkg provided DLLs" : os.path.join("build_64", "release") + r"\*.dll"
                                  }
                      )
    
    # For debug builds, only copy api*.dll for UCRT redist, then copy
    # the specific ucrt debug DLL in the extra copy arg.
    collect_main_files("x86 Debug", r"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\redist\debug_nonredist\x86\Microsoft.VC140.DebugCRT\*.dll",
                       r"C:\Program Files (x86)\Windows Kits\10\Redist\ucrt\DLLs\x86\api*.dll",
                       os.path.join("build_32", "debug"),
                       os.path.join("deploy", "release32_debug"),
                       extra_wc = {
                                    "UCRT Debug" : r"C:\Program Files (x86)\Windows Kits\10\bin\x86\ucrt\*.dll",
                                    "vcpkg provided DLLs" : os.path.join("build_32", "debug") + r"\*.dll"
                                  }
                      )
    collect_main_files("x64 Debug", r"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\redist\debug_nonredist\x64\Microsoft.VC140.DebugCRT\*.dll",
                       r"C:\Program Files (x86)\Windows Kits\10\Redist\ucrt\DLLs\x64\api*.dll",
                       os.path.join("build_64", "debug"),
                       os.path.join("deploy", "release64_debug"),
                       extra_wc = {
                                    "UCRT Debug" : r"C:\Program Files (x86)\Windows Kits\10\bin\x64\ucrt\*.dll",
                                    "vcpkg provided DLLs" : os.path.join("build_64", "debug") + r"\*.dll"
                                  }
                      )
    
    # Static builds
    # Release
    collect_static_main_files("x86 Static", os.path.join("build_static_32", "release"), os.path.join("deploy_static", "release32"),
                       #extra_wc = {
                       #             "EGL Library" : r"C:\Qt\Qt5.12.0-static\bin\libEGL.dll",
                       #             "GLESv2 Library" : r"C:\Qt\Qt5.12.0-static\bin\libGLESv2.dll",
                       #             "DirectX Compiler Library" : r"C:\Qt\5.12.0\msvc2015\bin\d3dcompiler_*.dll",
                       #             "Mesa OpenGL Software Rendering Library" : r"C:\Qt\5.12.0\msvc2015\bin\opengl32sw.dll",
                       #           }
                      )
    collect_static_main_files("x64 Static", os.path.join("build_static_64", "release"), os.path.join("deploy_static", "release64"),
                       #extra_wc = {
                       #             "EGL Library" : r"C:\Qt\Qt5.12.0x64-static\bin\libEGL.dll",
                       #             "GLESv2 Library" : r"C:\Qt\Qt5.12.0x64-static\bin\libGLESv2.dll",
                       #             "DirectX Compiler Library" : r"C:\Qt\5.12.0\msvc2015_64\bin\d3dcompiler_*.dll",
                       #             "Mesa OpenGL Software Rendering Library" : r"C:\Qt\5.12.0\msvc2015_64\bin\opengl32sw.dll",
                       #           }
                      )
    
    # Debug
    collect_static_main_files("x86 Static Debug", os.path.join("build_static_32", "debug"), os.path.join("deploy_static", "release32_debug"),
                       #extra_wc = {
                       #             "EGL Library" : r"C:\Qt\Qt5.12.0-static\bin\libEGLd.dll",
                       #             "GLESv2 Library" : r"C:\Qt\Qt5.12.0-static\bin\libGLESv2d.dll",
                       #             "DirectX Compiler Library" : r"C:\Qt\5.12.0\msvc2015\bin\d3dcompiler_*.dll",
                       #             "Mesa OpenGL Software Rendering Library" : r"C:\Qt\5.12.0\msvc2015\bin\opengl32sw.dll",
                       #           }
                      )
    collect_static_main_files("x64 Static Debug", os.path.join("build_static_64", "debug"), os.path.join("deploy_static", "release64_debug"),
                       #extra_wc = {
                       #             "EGL Library" : r"C:\Qt\Qt5.12.0x64-static\bin\libEGLd.dll",
                       #             "GLESv2 Library" : r"C:\Qt\Qt5.12.0x64-static\bin\libGLESv2d.dll",
                       #             "DirectX Compiler Library" : r"C:\Qt\5.12.0\msvc2015_64\bin\d3dcompiler_*.dll",
                       #             "Mesa OpenGL Software Rendering Library" : r"C:\Qt\5.12.0\msvc2015_64\bin\opengl32sw.dll",
                       #           }
                      )
    
    # Qt files only needed for dynamic builds
    collect_qt_files("x86", qt5_bin_dir_dynamic_32 + r"\windeployqt.exe", r"deploy\release32", r'build_32\release\CEmu.exe')
    collect_qt_files("x64", qt5_bin_dir_dynamic_64 + r"\windeployqt.exe", r"deploy\release64", r'build_64\release\CEmu.exe')
    
    collect_qt_files("x86 Debug", qt5_bin_dir_dynamic_32 + r"\windeployqt.exe", r"deploy\release32_debug", r'build_32\debug\CEmu.exe')
    collect_qt_files("x64 Debug", qt5_bin_dir_dynamic_64 + r"\windeployqt.exe", r"deploy\release64_debug", r'build_64\debug\CEmu.exe')
    
    file_list_32 = build_file_list("x86", r"deploy\release32")
    file_list_64 = build_file_list("x64", r"deploy\release64")
    
    file_list_32_debug = build_file_list("x86 Debug", r"deploy\release32_debug")
    file_list_64_debug = build_file_list("x64 Debug", r"deploy\release64_debug")
    
    file_list_32_static = build_file_list("x86", r"deploy_static\release32")
    file_list_64_static = build_file_list("x64", r"deploy_static\release64")
    
    file_list_32_static_debug = build_file_list("x86 Debug", r"deploy_static\release32_debug")
    file_list_64_static_debug = build_file_list("x64 Debug", r"deploy_static\release64_debug")
    
    # Build our ZIPs!
    cemu_win32_zip_fn = snap_base_path + "-win32-release-shared.zip"
    cemu_win64_zip_fn = snap_base_path + "-win64-release-shared.zip"
    
    cemu_win32_debug_zip_fn = snap_base_path + "-win32-debug-shared.zip"
    cemu_win64_debug_zip_fn = snap_base_path + "-win64-debug-shared.zip"
    
    cemu_win32_static_zip_fn = snap_base_path + "-win32-release-static.zip"
    cemu_win64_static_zip_fn = snap_base_path + "-win64-release-static.zip"
    
    cemu_win32_static_debug_zip_fn = snap_base_path + "-win32-debug-static.zip"
    cemu_win64_static_debug_zip_fn = snap_base_path + "-win64-debug-static.zip"
    
    make_zip("x86", cemu_win32_zip_fn, file_list_32)
    make_zip("x64", cemu_win64_zip_fn, file_list_64)
    
    make_zip("x86 Debug", cemu_win32_debug_zip_fn, file_list_32_debug)
    make_zip("x64 Debug", cemu_win64_debug_zip_fn, file_list_64_debug)
    
    make_zip("x86 Static", cemu_win32_static_zip_fn, file_list_32_static)
    make_zip("x64 Static", cemu_win64_static_zip_fn, file_list_64_static)
    
    make_zip("x86 Static Debug", cemu_win32_static_debug_zip_fn, file_list_32_static_debug)
    make_zip("x64 Static Debug", cemu_win64_static_debug_zip_fn, file_list_64_static_debug)
    
    # Upload everything!
    upload_snapshot(cemu_win32_zip_fn, cur_timestamp, snap_base_fn, bintray_api_username, bintray_api_key)
    upload_snapshot(cemu_win64_zip_fn, cur_timestamp, snap_base_fn, bintray_api_username, bintray_api_key)
    
    upload_snapshot(cemu_win32_debug_zip_fn, cur_timestamp, snap_base_fn, bintray_api_username, bintray_api_key)
    upload_snapshot(cemu_win64_debug_zip_fn, cur_timestamp, snap_base_fn, bintray_api_username, bintray_api_key)
    
    upload_snapshot(cemu_win32_static_zip_fn, cur_timestamp, snap_base_fn, bintray_api_username, bintray_api_key)
    upload_snapshot(cemu_win64_static_zip_fn, cur_timestamp, snap_base_fn, bintray_api_username, bintray_api_key)
    
    upload_snapshot(cemu_win32_static_debug_zip_fn, cur_timestamp, snap_base_fn, bintray_api_username, bintray_api_key)
    upload_snapshot(cemu_win64_static_debug_zip_fn, cur_timestamp, snap_base_fn, bintray_api_username, bintray_api_key)
    
    print(" * Snapshot deployment complete!")
    
def usage(msg = None):
    if msg:
        print(msg)
    
    print("Usage: %s [make_checksum|install|deploy]" % sys.argv[0])
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        usage()
        sys.exit(1)
    
    if sys.argv[1] == "make_checksum":
        make_checksum()
    elif sys.argv[1] == "install":
        install_deps()
    elif sys.argv[1] == "deploy":
        deploy_snapshots()
    else:
        usage("ERROR: Invalid command!")
