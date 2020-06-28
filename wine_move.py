'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.02

Take a list of files (local and remote)
if the remote file is more current (name or timestamp)
bring the remote file local

'''

import kvutil

import os
import subprocess
from shutil import copyfile
import sys

# logging - 
import kvlogger
# config=kvlogger.get_config(kvutil.filename_create(__file__, filename_ext='log'), loggerlevel='DEBUG')
config=kvlogger.get_config(kvutil.filename_create(__file__, filename_ext='log'))
kvlogger.dictConfig(config)
logger=kvlogger.getLogger(__name__)

# added logging feature to capture and log unhandled exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception



# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.02',
        'description' : 'defines the version number for the app',
    },
    'test' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we are running in test mode',
    },
    'debug' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'defines if we are running in debug mode',
    },
    'verbose' : {
        'value' : 1,
        'type'  : 'int',
        'description' : 'defines the display level for print messages',
    },
    'emulate' : {
        'value' : False,
        'type'  : 'bool',
        'description' : 'if true display actions but do not do them, if false take action',
    },
    'winecollection_glob_local' : {
        'value' : os.path.expanduser('~public/Documents/Doc/Wine/Wine Collection*.xls*'),
        'description' : 'defines the list of wine to search for when in test mode',
    }, 
    'winecollection_cloud_dir' : {
        'value' : os.path.expanduser('~/Dropbox/Private/Wine'),
        'description' : 'defines the path to the cloud directory housing wine collection files',
    },
    'winecollection_cloud_ncrypted' : {
        'value' : True,
        'type'  : 'bool',
        'description' : 'defines if the file in the cloud is nCrypted',
    },
    'ncrypted_exe' : {
        'value' :  os.path.expanduser('~/AppData/Roaming/nCryptedCloud/bin/ZipCipher64.exe'),
        'description' : 'path to the executable used to decrypt cloud files',
    },
    'copylocallist' : {
        'value' : ['wineref.csv','winedel.csv','wine_xref.csv','wine_xlat.csv','winestoreproximity.csv','winedescr_def.csv'],
        'type'  : 'liststr',
        'description' : 'defines the list of files we compare local and remote dir',
    },
    'localdir' : {
        'value' : './',
        'description' : 'defines the path to where local files reside',
    },
    'remotedir' : {
        'value' : os.path.expanduser('~/Dropbox/Linuxshare/wine'),
        'description' : 'defines the remote directory in cloud storage that has copies of files',
    },
    'copytype' : {
        'value' : 'local',
        'type'  : 'inlist',
        'valid' : ['local','remote','both'],
        'description' : 'defines in which direction we are syncing/updating',
    },
    'timediffcopy' : {
        'value' : 50,
        'type'  : 'int',
        'description' : 'defines the amount of time difference once exceeded we copy files',
    },
}


# do work to get alignment on the wine collection files and directories
def setOptionDictVariables( optiondict, debug=False ):
    # wine collection local filename split up
    wcl_path, wcl_filename = os.path.split( optiondict['winecollection_glob_local'] )
    logger.debug('optiondict[winecollection_glob_local].....:%s', optiondict['winecollection_glob_local'])
    logger.debug('wcl_path..................................:%s', wcl_path)
    logger.debug('wcl_filename..............................:%s', wcl_filename)
    
    # wine collection split into filename and extension parts
    wc_file, wc_ext = os.path.splitext( wcl_filename)
    logger.debug('wc_file...................................:%s', wc_file)
    logger.debug('wc_ext....................................:%s', wc_ext)

    # set the directory where the local wine files are kept
    optiondict['winecollection_local_dir'] = wcl_path
    logger.debug('optiondict[winecollection_local_dir]......:%s', optiondict['winecollection_local_dir'])

    # calculate and set the variable that defines the glob for remote wine collection files
    optiondict['winecollection_glob_cloud'] = os.path.join(optiondict['winecollection_cloud_dir'], wcl_filename)
    
    # add the zip if we are ncrypted
    if optiondict['winecollection_cloud_ncrypted']:
        optiondict['winecollection_glob_cloud'] += '.zip'
    logger.debug('optiondict[winecollection_glob_cloud].....:%s', optiondict['winecollection_glob_cloud'])
    logger.debug('optiondict[winecollection_glob_local].....:%s', optiondict['winecollection_glob_local'])

def rename_backup( srcfile, optiondict, bak_ext='.bak', debug=False ):
    fpath,fext = os.path.splitext( srcfile )
    if bak_ext[:1] != '.':
        bak_ext = '.' + bak_ext
    fpath_bak = os.path.join( fpath + bak_ext )
    if os.path.isfile( fpath_bak ):
        logger.info('remove_filename:%s', fpath_bak)
        if not optiondict['emulate']:
            kvutil.remove_filename( fpath_bak )
    logger.info('rename:%s:to:%s', srcfile,fpath_bak)
    if not optiondict['emulate']:
        os.rename( srcfile, fpath_bak )
        
def copy_decrypt( srcfile_enc, destfile_clear, optiondict, debug=False ):
    destpath = os.path.dirname(destfile_clear)
    logger.info('%s %s %s %s', optiondict['ncrypted_exe'],'-d', srcfile_enc, destpath)
    if not optiondict['emulate']:
        logger.debug('copy_decrypt file src:%s', srcfile_enc)
        logger.debug('copy_decrypt file src:%s', srcfile_enc[:-4])
        logger.debug('copy_decrypt file dst:%s', destfile_clear)
        logger.debug('copy_decrypt destpath:%s', destpath)
        logger.debug('copy_decrypt exe.....:%s', optiondict['ncrypted_exe'])
        #srcfile_enc = srcfile_enc[:-4]
        # out = subprocess.Popen([ optiondict['ncrypted_exe'],'-d', '"{}"'.format(srcfile_enc[:-4]), '"{}"'.format(destpath)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        # out = subprocess.Popen([ optiondict['ncrypted_exe'],'-d', '{}'.format(srcfile_enc), '{}'.format(destpath)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = subprocess.Popen([ optiondict['ncrypted_exe'],'-d', srcfile_enc, destpath], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout,stderr = out.communicate()
        logger.info('stdout:%s', stdout)
        logger.info('stderr:%s', stderr)

def copy_ncrypt( srcfile_clear, destfile_enc, optiondict, debug=False ):
    destpath = os.path.dirname(destfile_enc)
    logger.info('%s %s %s %s', optiondict['ncrypted_exe'],'-e', srcfile_clear, destpath)
    if not optiondict['emulate']:
        logger.debug('copy_ncrypt file src:%s', srcfile_clear)
        logger.debug('copy_ncrypt file dst:%s', destfile_enc)
        logger.debug('copy_ncrypt destpath:%s', destpath)
        logger.debug('copy_ncrypt exe.....:%s', optiondict['ncrypted_exe'])
        #out = subprocess.Popen([ optiondict['ncrypted_exe'],'-e', '"{}"'.format(srcfile_clear), '"{}"'.format(destpath)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        # out = subprocess.Popen([ optiondict['ncrypted_exe'],'-e', '{}'.format(srcfile_clear), '{}'.format(destpath)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = subprocess.Popen([ optiondict['ncrypted_exe'],'-e', srcfile_clear, destpath], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout,stderr = out.communicate()
        logger.info('stdout:%s', stdout)
        logger.info('stderr:%s', stderr)


def copy_clear( srcfile_clear, destfile_clear, optiondict, debug=False ):
    logger.info('copyfile:%s:to:%s', srcfile_clear, destfile_clear)
    if not optiondict['emulate']:
        copyfile(srcfile_clear, destfile_clear)

def copy_local( srcfile, destfile, optiondict, debug=False ):
    if optiondict['copytype'] in ('local','both'):
        logger.info('%s:%s', srcfile, destfile)
        if optiondict['winecollection_cloud_ncrypted']:
            copy_decrypt( srcfile, destfile, optiondict, debug )
        else:
            copy_clear( srcfile, destfile, optiondict, debug )

def copy_remote( srcfile, destfile, optiondict, debug=False ):
    if optiondict['copytype'] in ('remote','both'):
        logger.info('%s:%s', srcfile, destfile)
        if optiondict['winecollection_cloud_ncrypted']:
            copy_ncrypt( srcfile, destfile, optiondict, debug )
        else:
            copy_clear( srcfile, destfile, optiondict, debug )

def copyWineCollectionFile( optiondict, debug=False ):

    ### File Attributes collection ####
    # set variables
    wcc_lg_path=wcc_lg_fname=wcl_lg_path=wcl_lg_fname=wcc_lg_fname_comp=''
    wcc_lg_mtime= wc=_lg_mtime=0

    logger.info('Update wine collection file')

    # the the largest cloud filename (full path)
    wcc_lg_fpath = kvutil.filename_maxmin( optiondict['winecollection_glob_cloud'], reverse=True )
    # the the largest local filename
    wcl_lg_fpath = kvutil.filename_maxmin( optiondict['winecollection_glob_local'], reverse=True )
    logger.info('winecollection_cloud_fullpath:%s', wcc_lg_fpath)
    logger.info('winecollection_local_fullpath:%s', wcl_lg_fpath)
    
    # convert fullpath to only path and filename and capture the modify timestamp
    if wcc_lg_fpath:
        wcc_lg_path,wcc_lg_fname = os.path.split( wcc_lg_fpath )
        wcc_lg_mtime = os.path.getmtime( wcc_lg_fpath )
    if wcl_lg_fpath:
        wcl_lg_path,wcl_lg_fname = os.path.split( wcl_lg_fpath )
        wcl_lg_mtime = os.path.getmtime( wcl_lg_fpath )

    
    # get a known filename that will be compared
    if wcc_lg_fname.endswith('.zip'):
        wcc_lg_fname_comp = wcc_lg_fname[:-4]
    else:
        wcc_lg_fname_comp = wcc_lg_fname

    ### File Comparison by Name and modify date #####
    logger.debug('winecollection_cloud_filename:%s', wcc_lg_fname_comp)
    logger.debug('winecollection_local_filename:%s', wcl_lg_fname)
    logger.debug('winecollection_cloud_mtime...:%s', wcc_lg_mtime)
    logger.debug('winecollection_local_mtime...:%s', wcl_lg_mtime)
    
    # now we do filename and modify date comparisons and take action
    if wcc_lg_fname_comp > wcl_lg_fname:
        # cloud filename is greater just copy over
        logger.info('cloud filename greater than local:%s:%s',  wcc_lg_fname_comp, wcl_lg_fname)
        copy_local( wcc_lg_fpath, os.path.join(optiondict['winecollection_local_dir'],wcc_lg_fname_comp),optiondict )
    elif wcc_lg_fname_comp < wcl_lg_fname:
        # local filename is greater than cloud just copy over
        logger.info('local filename greater than cloud:%s:%s',  wcl_lg_fname, wcc_lg_fname_comp)
        copy_remote( wcl_lg_fpath, os.path.join(optiondict['winecollection_cloud_dir'], wcl_lg_fname),optiondict )
    elif wcc_lg_mtime > wcl_lg_mtime:
        if abs(wcc_lg_mtime - wcl_lg_mtime) > optiondict['timediffcopy']:
            # filenames the SAME - cloud file has a later timestamp
            logger.info('same filenames-cloud has later timestamp:%s:%s:%s', wcc_lg_mtime, wcl_lg_mtime, abs(wcc_lg_mtime - wcl_lg_mtime))
            copy_local( wcc_lg_fpath, os.path.join(optiondict['winecollection_local_dir'],wcc_lg_fname_comp),optiondict )
        else:
            logger.debug('same filenames-cloud has later timestamp but diff less than range:%s:%s:%s', wcc_lg_mtime, wcl_lg_mtime, optiondict['timediffcopy'] )
    elif wcc_lg_mtime < wcl_lg_mtime:
        if abs(wcc_lg_mtime - wcl_lg_mtime) > optiondict['timediffcopy']:
            # filenames the SAME - local file has a later timestamp
            logger.info('same filenames-local has later timestamp:%s:%s:%s', wcl_lg_mtime, wcc_lg_mtime,  abs(wcc_lg_mtime - wcl_lg_mtime) )
            copy_remote( wcl_lg_fpath, os.path.join(optiondict['winecollection_cloud_dir'], wcl_lg_fname),optiondict )
        else:
            logger.debug('same filenames-local has later timestamp but diff less than range:%s:%s:%s', wcl_lg_mtime, wcc_lg_mtime, optiondict['timediffcopy'] )
    else:
        # they are the same - no action take
        logger.info('no action taken - same filename - same timestamp')
        pass


def copyLatestFileNoNcrypt( optiondict, debug=False ):
    logger.info('comparing files-copytype:%s',optiondict['copytype'])
    logger.info('localdir................:%s',optiondict['localdir'])
    logger.info('remotedr................:%s',optiondict['remotedir'])

    for fname in optiondict['copylocallist']:
        logger.info('Analyzing file..........:%s',fname)

        lfname = os.path.join(optiondict['localdir'], fname)
        rfname = os.path.join(optiondict['remotedir'], fname)
    
        lmtime = os.path.getmtime( lfname )
        rmtime = os.path.getmtime( rfname )

        if rmtime > lmtime:
            if optiondict['copytype'] in ('local','both'):
                # remote file is later
                logger.info('%s:remote time stamp later:%s:%s', fname, rmtime, lmtime)
                rename_backup( lfname, optiondict )
                copy_clear( rfname, lfname, optiondict, debug )
        elif rmtime < lmtime:
            if optiondict['copytype'] in ('remote','both'):
                # local file is later
                logger.info('%s:local time stamp later:%s:%s', fname, rmtime, lmtime)
                rename_backup( rfname, optiondict )
                copy_clear( lfname, rfname, optiondict, debug )
            
# ---------------------------------------------------------------------------
if __name__ == '__main__':

    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    setOptionDictVariables( optiondict, debug=False )

    copyWineCollectionFile( optiondict, debug=False )
    
    copyLatestFileNoNcrypt( optiondict, debug=False )
