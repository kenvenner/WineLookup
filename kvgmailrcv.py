'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.11

Library of tools used read in and process gmail mailbox
'''

import time
import imaplib
import email
import mailparser
import os
import datetime
import base64
import html2text
#import kvutil

# logging
import logging
logger = logging.getLogger(__name__)

# tells if we are printing out debug message
debug = False

# version number
AppVersion = '1.11'

# todo
# 1) we have a possible problem with creating a unique directory based on msgid - need to determine if we want to fix


# build loggers
def setup_logger(name, log_file, level=logging.INFO):
    """Function setup as many loggers as you want"""

    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    
    handler = logging.FileHandler(log_file)        
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger

# generate a unique-email ID - generally used to save things to folders/files
def _generate_uid(msgid):
    return datetime.datetime.today().strftime('%Y-%m-%d-%H-%M-%S') + '-msg-' + str(msgid)

# create the enhanced email reading object
#   login - if user/password are set
#           if logged in - change the folder the defined folder
#
def init( email_setting ):
    verbose = 0

    logger.info('init:start')
    
    # capture the debugging flag
    if 'imap_debug' in email_setting.keys() and email_setting['imap_debug']:
        verbose = email_setting['imap_debug']
        logger.info('init:imap_debug set')
        
    # check that we have the required values set
    missing_count = 0
    for setting in ('imap_server', 'imap_folder'):
        if setting not in email_setting.keys():
            missing_count += 1
            logger.info('init:required-setting-MISSING: %s', setting)
        elif not email_setting[setting]:
            missing_count += 1
            logger.info('init:required-setting-BLANK: %s', setting)

    # if we are missing setting we are done
    if missing_count:
        if verbose: logger.info('init:missing count: %s %s', missing_count, ' - return 0')
        return 0

    # create the imap object
    try:
        logger.debug('ssl-connection-with:' + email_setting['imap_server'])
        # create an IMAP object
        mail = imaplib.IMAP4_SSL(email_setting['imap_server'])
    except Exception as e:
        logger.critical( 'init-exception:' + str(e) )
        return 0

    # if the user provided the user and password then login along with init
    skip_login = False
    for setting in ('user', 'password'):
        if not setting in email_setting.keys():
            # value is missing
            skip_login = True
        elif not email_setting[setting]:
            # value is blank
            skip_login = True


    # do the login if we should do the login
    if not skip_login:
        # debugging
        if verbose: logger.info('init:login and go to folder: %s', email_setting['imap_folder'])
        # if the login failed - return zero
        if not login(mail, email_setting['user'], email_setting['password']):
            if debug: print('init:not_skip_login:failed to login')
            return 0
        else:
            # think we are not going to do this
            
            # we have logged in - did the user send in a folder - if so set the folder
            if email_setting['imap_folder']:
                msglist = select_folder(mail, email_setting['imap_folder'])
                return mail
            else:
                logger.info('login:folder-NOTSELECTED')

    # return true - we are successful
            
    elif verbose:
        logger.info('init:login-SKIPPED')

    # debug
    if debug: print('login:type:', type(mail))
    

    # return the imap object created
    return mail

# login to an imap object
def login(mail, user, password):

    try:
        # login to the server with teh email/passwor
        rv, data = mail.login(user,password)
    except Exception as e:
        logger.info( 'login-exception: %s', str(e) )
        return 0
    
    # validate we got logged in ok
    if rv != 'OK':
        logger.debug('login:Not able to sign in!')
        raise

    return 1

# list out (print) the folders in this mailbox
def list_folder(mail):
    try:
        rv, data = mail.list()
        print('list_folder:', data)
        print('-'*60)
        for row in data:
            print(row)
        print('-'*60)

        # return success
        return True

    except Exception as e:
        print('list_folder:Exception:', str(e))
        return 0

# create a folder
def create_folder(mail, folder):
    # assure the passed in folder name is quoted
    folder = quote_string_containing_spaces(folder)
    
    try:
        rv, data = mail.create(folder)
        if rv != 'OK':
            logger.critical('create_folder:create-folder-problem: %s', data)
            return 0

        # return success
        return True
    except Exception as e:
        logger.critical('create_folder:Exception: %s', str(e))
        return 0

# delete a folder
def delete_folder(mail, folder):
    # assure the passed in folder name is quoted
    folder = quote_string_containing_spaces(folder)
    
    try:
        rv, data = mail.delete(folder)
        if rv != 'OK':
            logger.critical('delete_folder:create-folder-problem: %s', data)
            return 0

        # return success
        return True
    except Exception as e:
        logger.critcal('delete_folder:Exception: %s', str(e))
        return 0


# select a folder for a logged in mail user
def select_folder_handle_exception(mail, folder):
    # assure the passed in folder name is quoted
    folder = quote_string_containing_spaces(folder)

    # debug
    if debug:
        print('kvgmailrcv:select_folder:mail.select(folder):folder:', folder)
        print('mail type:', type(mail))
    
    try:
        rv, data = mail.select(folder)
        if rv != 'OK':
            logger.critcal('select_folder:folder-selection-problem: %s', data)
            return 0
        
        # return this array
        return search_messages(mail)

    except Exception as e:
        logger.critical( 'select_folder:Exception: %s', str(e) )
        return 0
    

# select a folder for a logged in mail user
def select_folder(mail, folder):
    # assure the passed in folder name is quoted
    folder = quote_string_containing_spaces(folder)

    # debug
    if debug:
        print('kvgmailrcv:select_folder:mail.select(folder):folder:', folder)
        print('mail type:', type(mail))
    
    rv, data = mail.select(folder)
    if rv != 'OK':
        logger.critcal('select_folder:folder-selection-problem: %s', data)
        return 0
        
    # return this array
    return search_messages(mail)


# get the messages in the current folder
def search_messages(mail):
    try:
        rv, data = mail.uid('search', None, "ALL") # search and return uids instead

        # check to see we got an OK - there were messages found
        if rv != 'OK':
            logger.info("search_messages:No messages found!")
            return 0
        
        # the list of mail ids is the first thing that is returned, convert to ASCII if required
        mail_ids = data[0].decode('ASCII')

        # return the list of ids
        return mail_ids.split()

    except Exception as e:
        logger.critical( 'search_messages:Exception: %s', str(e) )
        return 0

# get list of capabilities for this mail account
def get_capability(mail):
    # extract the capability
    rv, data = mail.capability()
    # return the list of capability
    return data[0].decode('ASCII').split()


# move one or mesages to a new folder
def move_message(mail, uid, folder):
    # make sure we have a string we can pass into as the folder
    folder = quote_string_containing_spaces(folder)

    try:
        # debugging
        logger.info('move_message:uid:%s:folder:%s', uid, folder)

        # ok, data = mail.copy(uid, folder)
        # ok, data = mail.uid('COPY', uid, folder)
        # ok, data = mail.uid('MOVE', uid, folder)
        # ok, data = mail.uid('STORE', uid , '+FLAGS', '(\Deleted)')

        # message copy
        if False:
            logger.info('move_message:mail.copy')
            ok, data = mail.copy(uid, folder)
            logger.info('data after copy: %s', data)
            
        # message uid copy
        if True:
            logger.info('move_message:mail.uid(copy)')
            ok, data = mail.uid('COPY', uid, folder)
            logger.info('data after copy: %s', data)
            
        # message stores
        if False:
            logger.info('move_message:mail.store-twice')
            ok, data  = mail.store(uid, '+X-GM-LABELS', folder)
            logger.info('store-ok:%s:data:%s', ok, data)
            ok, data  = mail.store(uid, '-X-GM-LABELS', '\\INBOX')
            logger.info('uid-ok:%s:data:%s', ok, data)
        
        # debugging
        newmailids = select_folder(mail, folder)
        logger.info('folder: %s \nnewmailids: %s', folder, newmailids)
        newmailids = select_folder(mail, 'inbox')
        logger.info('folder:inbox\nnewmailids: %s', newmailids)

        if False and ok != 'OK':
            logger.critical('move_message:cannot copy uid:%s to folder:%s', uid, folder_quoted)
            raise

        logger.info('move_message:call delete_message')
        delete_message(mail, uid)

        return True
    
    except Exception as e:
        logger.critical('e: %s', str(e))
        if str(e) == "COPY command error: BAD [b'Could not parse command']":
            logger.info( 'move_message:to_folder: %s %s %s', folder, ':Exception: Invalid folder' )
        else:
            logger.info( 'move_message:to_folder: %s %s %s', folder, ':Exception:', str(e) )
        return 0

# delete one message
def delete_message(mail, uid):

    try:
        # debugging
        logger.debug('delete_message:uid:%s', uid)
        
        # move to trash m.uid
        if False:
            logger.debug('delete_messgae:trash')
            ok, data = mail.uid('STORE', uid, '+X-GM-LABELS', '\\Trash')
            logger.debug('delete_message:rv:%s:data:%s', rv, data)

        # delete the message m.store
        if False:
            logger.debug('delete_messgae:deleted')
            rv, data = mail.store( uid, '+FLAGS', '\\Deleted' )
            rv, data = mail.store( uid, '+FLAGS', '\\Deleted' )
            logger.debug('delete_message:rv:%s:data:%s', rv, data)

        # delete the message 2 m.store
        if False:
            logger.debug('delete_messgae:deleted')
            rv, data = mail.store( uid, '+FLAGS', '(\\Deleted)' )
            logger.debug('delete_message:rv:%s:data:%s', rv, data)
            
        # delete the message 3 (m.uid)
        if True:
            logger.debug('delete_messgae:m.uid-deleted')
            #rv, data = mail.uid( 'STORE', uid, '+FLAGS', '\\Deleted' )
            rv, data = mail.uid( 'STORE', uid, '+FLAGS', '(\Deleted)' )
            logger.debug('delete_message:rv:%s:data:%s', rv, data)
            
        if rv != 'OK':
            logger.critical('delete_message:cannot delete uid:%s:data:%s', uid, data)
            raise

        if True:
            logger.debug('deleted_message:expunge')
            data = mail.expunge()
            logger.debug('delete_message:data:%s', data)

        return True

    except Exception as e:
        logger.critical( 'delete_message:Exception: %s', str(e) )
        return 0

    
# get the next message from list of messages and return mparse nad remaining list of messages
def get_next_imap_msg(mail, mail_ids):

    # show what you are looking for
    logger.info('get_next_imap_msg:msgid: %s', ','.join(mail_ids))

    # get the message indiciated
    mparse = get_imap_msg( mail, mail_ids[0] )

    # 
    if mparse:
        logger.info('get_next_imap_msg: pull off first time and return the remainder of the list')
        return (mparse, mail_ids[1:])
    else:
        logger.info('get_next_imap_msg:no message parsed')
        return (None, mail_ids)
    
# get an imap message in the object format we know about
def get_imap_msg(mail, msgid):

    # show what you are looking for
    logger.info('get_imap_msg:msgid: %s', msgid)
    print('get_imap_msg:msgid:',msgid)
    
    # capture issues with getting a message
    try:
        # get the object
        rv, data = mail.uid('fetch', msgid, '(RFC822)')
        
        # check the status of the fetch - error out if required
        if rv != 'OK':
            logger.critical('get_imap_msg:ERROR getting message: %s:%s', msgid, data)
            print('get_imap_msg:ERROR getting message: %s:%s', msgid, data)
            return 0
            
        # debugging
        logger.debug('get_imap_msg:fetched-mail-rv: %s', rv)
        logger.debug('--------------------------------------------')
        logger.debug('get_imap_msg:data-count: %s', len(data))
        logger.debug('--------------------------------------------')
        logger.debug('get_imap_msg:fetched-mail-data: %s', data)
        logger.debug('--------------------------------------------')
        
        # this should be the raw emailmessage - that we need to convert
        raw_email = data[0][1]

        # debugging
        logger.info('get_imap_msg:raw_email-type-bytes: %s', isinstance(raw_email, bytes))
        logger.info('--------------------------------------------')

        # parse message based on message type
        if isinstance(raw_email, bytes):
            mparse = mailparser.parse_from_bytes(raw_email)
        else:
            mparse = mailparser.parse_from_string(raw_email)

        # add attributes to the new object
        mparse.mime_str = raw_email
        mparse.msgid = mparse.msgUID = msgid
        mparse.uid = mparse.msgGUID = _generate_uid(msgid)
        mparse.cc_email = [x[1] for x in mparse.cc]
        mparse.to_email = [x[1] for x in mparse.to]
        mparse.from_email = [x[1] for x in mparse.from_]

        # debugging
        if debug: dump_mparse(mparse)

        
    except Exception as e:
        logger.critical( 'get_imap_msg:Exception: %s', str(e) )
        return 0

    # return the mparse object
    return mparse

    
# read in a MIME file and put it in a parsed message format 
def get_imap_file( fullfilename ):

    # show what you are looking for
    logger.info('get_imap_file:fullfilename: %s', fullfilename)

    # capture issues with getting a message
    try:
        # load the message from a file
        mparse = mailparser.parse_from_file( fullfilename )

        # debugging
        logger.info('get_imap_file:setting-mparse-attributes')
        
        # add attributes to the new object
        # read in the file into a string
        mparse.msgid = 1
        mparse.uid = _generate_uid(mparse.msgid)
        with open( fullfilename, 'r') as myfile:
            mparse.mime_str = myfile.read()
        
        # debugging
        dump_mparse(mparse)

        
    except Exception as e:
        logger.critical( 'Exception: %s', str(e) )
        return 0
    
    # return the mparse object
    return mparse


#------------ DUMP Print ----------------------------------------------------
def dump_email_msg(email_msg):
    skip_keys = ['mime_str','mime_attachments']

    print('------------ EMAIL_MSG START ---------------')
    for key in email_msg.keys():
        if key not in skip_keys:
            print(key, ':', email_msg[key])
        else:
            print(key, ': <did not output this item in this run>')

        print('--------------------------------------------')
            
def dump_msg(msg, attachments):
    dump_verbose = False
    
    print('------------ MSG START ---------------------')
    if dump_verbose:
        print('msg:', msg)
    else:
        print('msg: <did not output this item in this run>')
    print('--------------------------------------------')
    print('items:', msg.items())
    print('--------------------------------------------')
    print('items-count:', len(msg.items()))
    print('--------------------------------------------')
    print('item-one-per-line:')
    for item in msg.items():
        print(item)
    print('--------------------------------------------')
    print('keys:', msg.keys())
    print('--------------------------------------------')
    print('keys-count:', len(msg.keys()))
    print('--------------------------------------------')
    print('attachments-len:', len(attachments))
    """for attach in attachments:
        print('att-filename:', attach['filename'])
        print('att-payload:', attach['payload'])"""
    print('------------ MSG END -----------------------')
        
def dump_mparse(mparse, calledFrom='', dump_verbose=False):
    
    print('==========================', calledFrom, 'start ========================================================')
    print('------------ MPARSE START ------------------')
    print('mparse:', mparse)
    print('--------------------------------------------')
    if mparse == None:
        print('==========================', calledFrom, 'end ======================================================')
        return
    if len(mparse.attachments) > 0:
        print('mparse.attachments.len:', len(mparse.attachments))
        print('mparse.attachments[0].keys():', mparse.attachments[0].keys())
        print('--------------------------------------------')
        if dump_verbose:
            print('mparse.attachments:', mparse.attachments)
            for att in mparse.attachments:
                print('att:',att)
                if att['content_transfer_encoding'] == 'base64':
                    print('==================')
                    print('att-base64:', att['filename'])
                    print(base64.b64decode(att['payload']))
                    print('==================')

        else:
            for att in mparse.attachments:
                print('filename.....................:', att['filename'])
                print('    binary...................:', att['binary'])
                print('    mail_content_type........:', att['mail_content_type'])
                print('    content-id...............:', att['content-id'])
                print('    content_transfer_encoding:', att['content_transfer_encoding'])
    else:
        print('mparse.attachment: <no attachments>')
        
    print('--------------------------------------------')
    print('mparse.body:', mparse.body)
    print('--------------------------------------------')
    print('mparse._text_html:len:', len(mparse._text_html))
    print('mparse._text_html:', mparse._text_html)
    print('--------------------------------------------')
    print('mparse._text_plain:len:', len(mparse._text_plain))
    print('mparse._text_plain:', mparse._text_plain)
    print('--------------------------------------------')
    print('mparse.date:', mparse.date)
    print('--------------------------------------------')
    print('mparse.defects:', mparse.defects)
    print('--------------------------------------------')
    print('mparse.defects_categories:', mparse.defects_categories)
    print('--------------------------------------------')
    print('mparse.delivered_to:', mparse.delivered_to)
    print('--------------------------------------------')
    print('mparse.from_:', mparse.from_)
    print('--------------------------------------------')
    print('mparse.get_server_ipaddress(trust="my_server_mail_trust"):', mparse.get_server_ipaddress(trust="my_server_mail_trust"))
    print('--------------------------------------------')
    print('mparse.headers:', mparse.headers)
    print('--------------------------------------------')
    print('mparse.headers-exploded:')
    for key in mparse.headers.keys():
        print('mparse.header:',key,":\n", mparse.headers[key])
    print('--------------------------------------------')
    if dump_verbose:
        print('mparse.mail:', mparse.mail)
    else:
        print('mparse.mail: <did not output this in this run>')
    print('--------------------------------------------')
    if dump_verbose:
        print('mparse.message:', mparse.message)
    else:
        print('mparse.message: <did not output this in this run>')
    print('--------------------------------------------')
    if dump_verbose:
        print('mparse.message_as_string:', mparse.message_as_string)
    else:
        print('mparse.message_as_string: <did not output this in this run>')
    print('--------------------------------------------')
    print('mparse.message_id:', mparse.message_id)
    print('--------------------------------------------')
    print('mparse.received:', mparse.received)
    print('mparse.received:byline:')
    for rline in mparse.received:
        print(rline)
    print('--------------------------------------------')
    print('mparse.subject:', mparse.subject)
    print('--------------------------------------------')
    print('mparse.text_plain:', mparse.text_plain)
    print('--------------------------------------------')
    print('mparse.cc:', mparse.cc)
    print('--------------------------------------------')
    print('mparse.to:', mparse.to)
    print('--------------------------------------------')
    print('mparse.to_domains:', mparse.to_domains)
    print('------------ MPARSE ADDED ------------------')
    print('mparse.mime_str:len:', len(mparse.mime_str))
    print('--------------------------------------------')
    print('mparse.msgid:', mparse.msgid)
    print('--------------------------------------------')
    print('mparse.uid:', mparse.uid)
    print('--------------------------------------------')
    print('mparse.msgUID:', mparse.msgUID)
    print('--------------------------------------------')
    print('mparse.msgGUID:', mparse.msgGUID)
    print('--------------------------------------------')
    print('mparse.to_email:', mparse.to_email)
    print('--------------------------------------------')
    print('mparse.cc_email:', mparse.cc_email)
    print('--------------------------------------------')
    print('mparse.from_email:', mparse.from_email)
    print('------------ MPARSE END --------------------')
    print('==========================', calledFrom, 'end ======================================================')


def msg_attachments(msg):
    print('------------ MSG_ATTACHMENTS START ---------')
    attachments = []
    # save out the attachments
    if msg.is_multipart():
        print('multipart-saving out attachments')
        for part in msg.walk():
            attachment = {}
            
            # capture the content type of this part
            attachment['mail_content_type'] = part.get_content_type()
            attachment['filename'] = part.get_filename()
            charset = part.get_content_charset('utf-8')            
            
            # debugging
            print('content-type:', attachment['mail_content_type'])
            print('filename:', attachment['filename'])
            print('charset:', charset)
            print('is_multipart:', part.is_multipart())
            
            # checks we perform
            if attachment['mail_content_type'] == 'multipart':
                print('part is multipart- skipping this part')
                print('===')
                continue
                    
            if part.get('Content-Disposition') is None:
                print('part has None Content-Disposition- skipping this part')
                print('get_content_subtype:', part.get_content_subtype())
                print('this shoudl be the payload')
                print('+++')
                print('payload:\n', part.get_payload(decode=True))
                print('===')
                continue


            # if there is a filename - then we will save this file to disk
            if bool(attachment['filename']):
                print(attachment['filename'], ":saving payload")
                attachment['payload'] = part.get_payload(decode=True)
                attachments.append(attachment)
            else:
                print('did not save attachment')

            print('===')

    else:
        print('not multi-part')
        
    print('------------ MSG_ATTACHMENTS END -----------')

    # return
    return attachments


#--------------- SAVE to the filesystem ----------------------------------

# save the mime, body, and attachments for a message
def save_message(mparse, basedir='msg'):

    # debugging
    logger.info('save_messsage:basedir: %s', basedir)
    
    # save the message as a MIME file
    msg_dir = save_mime_msg(mparse, basedir)
    
    # save bod to the directory
    save_body_msg(mparse, basedir)
    
    # save attachments to the directory
    save_attachments(mparse, basedir)
    
    # return the msg_dir
    return msg_dir



# this function takes all attachments and saves them as unique filenames in the basedir
def save_attachments(mparse, basedir='msg'):

    # debugging
    logger.info('save_attachments:basedir: %s', basedir)
    
    # no action if there are no attachments
    if len(mparse.attachments) == 0:
        # debugging
        logger.info('save_attachments:no-attachments:no-action taken')
        return 0 

    # create the directory to house the files from this email message
    msg_dir = _create_msg_dir(basedir, mparse.uid)

    # create a message counter and content type extension definition
    msgcounter = 1
    content_type_extension = {
	'text/html'  : '.html',
	'text/plain' : '.txt',
    }
    
    # step through the attachments (these are rows of dictionaries)
    for att in mparse.attachments:
        # create a filename for this attachment
        filename = att['filename']
        if not filename:
            # filename not provided - generate one
            file_ext = ''
            if att['mail_content_type'] in content_type_extension.keys():
                file_ext = content_type_extension[att['mail_content_type']]
            filename = ''.join(['msg-', str(msgcounter), file_ext])
        # create the file and output the data
        if att['binary'] and att['content_transfer_encoding'] == 'base64':
            with open(os.path.join(msg_dir, filename), 'wb') as temp_file:
                temp_file.write(base64.b64decode(att['payload']))
        else:
            with open(os.path.join(msg_dir, filename), 'wb') as temp_file:
                temp_file.write(att['payload'])
        # increment counter
        msgcounter += 1

        # debugging - display the file just created
        logger.info('save_attachments:outfile: %s', os.path.join(msg_dir, filename))

    # return the msg_dir
    return msg_dir

# this function saves the body (HTML and TEXT) to files
def save_body_msg(mparse, basedir='msg'):

    # debugging
    logger.info('save_body_msg:basedir: %s', basedir)
    
    # create the directory to house the files from this email message
    msg_dir = _create_msg_dir(basedir, mparse.uid)

    # if there is an HTML body
    if mparse.text_html:
        filename = ''.join(['msg-body-', mparse.uid, '.html'])
        with open(os.path.join(msg_dir, filename), 'w') as temp_file:
            temp_file.write("\n".join(mparse.text_html))

        # debugging - display the file just created
        logger.info('save_body_msg:text_html:outfile: %s', os.path.join(msg_dir, filename))

    # if there is an plain text body
    if mparse.text_plain:
        filename = ''.join(['msg-body-', mparse.uid, '.txt'])
        with open(os.path.join(msg_dir, filename), 'w') as temp_file:
            temp_file.write("\n".join(mparse.text_plain))

        # debugging - display the file just created
        logger.info('save_body_msg:text_plain:outfile: %s', os.path.join(msg_dir, filename))

    # return the msg_dir
    return msg_dir

# save the processed message MIME structure as a file
def save_mime_msg(mparse, basedir):

    # debugging
    logger.info('save_mime_msg:basedir: %s', basedir)

    # create the directory to house the files from this email message
    msg_dir = _create_msg_dir(basedir, mparse.uid)

    filename = ''.join(['msg-', mparse.uid, '.mime'])
    with open(os.path.join(msg_dir, filename), 'wb') as temp_file:
        temp_file.write(mparse.mime_str)

    # debugging - display the file just created
    logger.info('save_body_msg:outfile: %s', os.path.join(msg_dir, filename))

    # return the msg_dir
    return msg_dir

# -------------------------------------------------
#
# Utility to read email from Gmail Using Python
#
# ------------------------------------------------

def read_email_from_gmail():
    try:
        # debugging
        print('smtp:', SMTP_SERVER, "\nfrom:", FROM_EMAIL, "\npwd:", FROM_PWD)

        # create an IMAP object - connected to the user
        mail = imaplib.IMAP4_SSL(SMTP_SERVER)

        # login to the server with teh email/passwor
        typ, accountDetails = mail.login(FROM_EMAIL,FROM_PWD)

        # validate we got logged in ok
        if typ != 'OK':
            print('Not able to sign in!')
            return

        # move the the selected folder
        mail.select(MAIL_FOLDER)

        # search the mail box - use UID search to get the UID back
        #rv, data = mail.search(None, 'ALL')
        rv, data = mail.uid('search', None, "ALL") # search and return uids instead

        # check to see we got an OK - there were messages found
        if rv != 'OK':
            print("No messages found!")
            return
        
        # the list of mail ids is the first thing that is returned, convert to ASCII if required
        mail_ids = data[0].decode('ASCII')

        # debugging
        print('rv:', rv)
        print("data:", data)
        print('mail_ids:', mail_ids)

        id_list = mail_ids.split()   
        first_email_id = int(id_list[0])
        latest_email_id = int(id_list[-1])

        # debugging
        print('id_list:', id_list)
        print('first:', first_email_id, "\nlatest:", latest_email_id)
        print('id_list-count', len(id_list))
        print('--------------------------------------------')

        # loop through the list of messages we got back
        # current - run backwards - may want to go forward in the future
        for i in id_list[::-1]:
            # debugging
            print ('i:', i)

            # get the message
            #rv, data = mail.fetch(i, '(RFC822)' )
            rv, data = mail.uid('fetch', i, '(RFC822)')

            # check the status of the fetch
            if rv != 'OK':
                print("ERROR getting message:", i)
                return
            
            # debugging
            print('fetched-mail-rv:', rv)
            print('--------------------------------------------')
            print('fetched-mail-data:', data)
            print('--------------------------------------------')
            print('data-count:', len(data))
            print('--------------------------------------------')

            # this should be the raw emailmessage - that we need to convert
            raw_email = data[0][1]

            # debugging
            print('raw_email:', raw_email, "\n\n")
            print('--------------------------------------------')
            print('raw_email-type-bytes:', isinstance(raw_email, bytes))

            # parse message based on message type
            if isinstance(raw_email, bytes):
                msg = email.message_from_bytes(raw_email)
                #mparse = mailparser.parse_from_bytes(raw_email)
            else:
                msg = email.message_from_string(raw_email)
                #mparse = mailparser.parse_from_string(raw_email)

            # debugging
            print('--------------------------------------------')
            print('msg:', msg)
            print('--------------------------------------------')
            print('items:', msg.items())
            print('--------------------------------------------')
            print('items-count:', len(msg.items()))
            print('--------------------------------------------')
            print('data-count:', len(data))
            print('--------------------------------------------')


            """print('mparse:', mparse)
            print('--------------------------------------------')
            print('mparse.attachments:', mparse.attachments)
            print('--------------------------------------------')
            print('mparse.body:', mparse.body)
            print('--------------------------------------------')
            print('mparse.date:', mparse.date)
            print('--------------------------------------------')
            print('mparse.defects:', mparse.defects)
            print('--------------------------------------------')
            print('mparse.defects_categories:', mparse.defects_categories)
            print('--------------------------------------------')
            print('mparse.delivered_to:', mparse.delivered_to)
            print('--------------------------------------------')
            print('mparse.from_:', mparse.from_)
            print('--------------------------------------------')
            print('mparse.get_server_ipaddress(trust="my_server_mail_trust"):', mparse.get_server_ipaddress(trust="my_server_mail_trust"))
            print('--------------------------------------------')
            print('mparse.headers:', mparse.headers)
            print('--------------------------------------------')
            print('mparse.mail:', mparse.mail)
            print('--------------------------------------------')
            print('mparse.message:', mparse.message)
            print('--------------------------------------------')
            print('mparse.message_as_string:', mparse.message_as_string)
            print('--------------------------------------------')
            print('mparse.message_id:', mparse.message_id)
            print('--------------------------------------------')
            print('mparse.received:', mparse.received)
            print('--------------------------------------------')
            print('mparse.subject:', mparse.subject)
            print('--------------------------------------------')
            print('mparse.text_plain:', mparse.text_plain)
            print('--------------------------------------------')
            print('mparse.to:', mparse.to)
            print('--------------------------------------------')
            print('mparse.to_domains:', mparse.to_domains)
            print('--------------------------------------------') """

            # save out the attachments
            if msg.is_multipart():
                print('multipart-saving out attachments')
                for part in msg.walk():
                    # capture the content type of this part
                    ctype = part.get_content_type()

                    # debugging
                    print('content-type:', ctype)
                    print('filename:', part.get_filename())

                    # checks we perform
                    if ctype == 'multipart':
                        print('part is multipart- skipping this part')
                        continue
                    
                    if part.get('Content-Disposition') is None:
                        print('part is Content-Disposition- skipping this part')
                        continue

                    # get the filename
                    fileName = part.get_filename()
                        

                    # if there is a filename - then we will save this file to disk
                    if bool(fileName):
                        # create a full path to the file if we have a filename
                        filePath = os.path.join(DIR_ATTACH, fileName)
                        # create a new file if one does not already exist
                        if not os.path.isfile(filePath):
                            print('save to disk:', filePath)
                            try:
                                fp = open(filePath, 'wb')
                                fp.write(part.get_payload(decode=True))
                                fp.close()
                            except Exception as e:
                                print('could not create:', filePath, ':', str(e))
                        else:
                            print('file-exists-not-saved-again:', filePath)

    except Exception as e:
        print( 'Exception::', str(e) )



#------------------------------------------------------------
# UTILITY FUNCTIONS
#------------------------------------------------------------

# utility function for the class
# quote a string if it has spaces
def quote_string_containing_spaces( value, quote_char="'" ):

    # debugging
    logger.debug('quote_string_containing_spaces: %s', value)

    # if there is no value return it
    if not value:
        # debugging
        logger.debug('quote_string_containing_spaces: there is no value')
        return value

    # if there are not spaces, just return the value we were passed
    if len(value.split()) < 2:
        # debugging
        logger.debug('quote_string_containing_spaces: no-spaces-no-action')
        return value

    # if the string starts and ends with the required quote_char
    if value.startswith(quote_char) and value.endswith(quote_char):
        # debugging
        logger.debug('quote_string_containing_spaces: already-quoted')
        # for now - assume it is delimted and go with it - we need to fix this logic though
        return value
    else:
        # we must quote all the internal quotes and then add quotes
        return quote_char + value.replace(quote_char, '\\' + quote_char) + quote_char

# REMOVE WHEN DONE TESTING ---  for testing quote a string if it has spaces
def qts( value, quote_char="'" ):
    if len(value.split()) < 2: return value
    if value.startswith(quote_char) and value.endswith(quote_char):
        return value
    else:
        return quote_char + value.replace(quote_char, '\\' + quote_char) + quote_char

# this function determines the message directory and creates if it does not exist
def _create_msg_dir( basedir, uid ):
    # debugging
    logger.debug('_create_msg_dir:basedir:%s:uid:%s ', basedir, uid)

    # create the directory to house the files from this email message
    msg_dir = os.path.join(basedir, uid)
    if not os.path.exists(msg_dir):
        # debugging
        logger.debug('_create_msg_dir:basedir:create-directory:%s', msg_dir)
        os.makedirs(msg_dir)
    return msg_dir

    
# utility function for the class - return the value in dict or a default value
def _setting_or_default( setting, setting_dict, default=None ):
    if setting in setting_dict:
        # debugging
        logger.debug('_setting_or_default:return-setting')
        return setting_dict[setting]
    else:
        # debugging
        logger.debug('_setting_or_default:return-default')
        return default
        


# ------------------ CLASS DEFINITITIONS --------------------
class GmailImap:
    # create the object - options in the passed in dictionary could be:
    #     verbose = (int) verbose level (opt)
    #     imap_debug = (int) imaplib debugging level (opt)
    #
    #     imap_server = (str) DNS string for the IMAP server (default: imap.gmail.com)
    #     imap_folder = (str) folder to read messages from (default: inbox) (self.folder_read)
    #
    #     imap_folder_pass = (str) folder to move mesages to if processed and passed (self.folder_pass)
    #     imap_folder_fail = (str) folder to move message to if porcessed and failed (self.folder_fail)
    #
    #     user = (str) username/email account of gmail account (eg. ken@vennerllc.com)
    #     password = (str) password for this gmail account
    #
    #     msgPath = (str) file system path to the root directory where messages are saved
    #
    #     fromIncludeEmails
    #     fromIncludeDomains
    #     fromExcludeIfNotInclude
    #     fromExcludeEmails
    #     fromExcludeDomains
    
    # created entities:
    #     imapobj - imaplib object used to interact with the mail account
    #     loggedIn - (bool) - have we successfully logged into this email account
    #     folder_current - (str) populated if we have successfully selected a folder
    #     mail_ids - (list int) - ids of email messages in folder_current
    #     msgParsed - (bool) - have we successfully read and parsed an email message
    #     msgProcessed - (bool) - have we successfully processed this message
    #     msgUID
    #     msgGUID
    #
    def __init__( self, email_setting={} ):

        # set up other attributes we are looking to manage
        self.loggedIn = False         # defines if imapobj is logged in as a user
        self.folder_current = None    # defines the current folder we are reading from
        self.mail_ids = []            # defines the list of mailids available in the current folder
        self.mparse = None            # the object model for the content of the last parsed MIME object
        self.user = None
        self.password = None
        self.msgPath = None           # filepath to the root directory where messages are saved (passed in)

        # calculated when parsing/procesing a message
        self.msgParsed = False        # defines if a message has been parsed
        self.msgProcessed = None      # defines if the message was successfully parsed/processed
        self.msgSaved = False         # defines if this message was successfully saved to the file system
        self.uidPath = None           # filepath to the directory that email files are deposited (created by calling _create_msg_dir)
        self.msgUID = None            # defines the UID of the message that was read in and parsed
        self.msgGUID = None           # defines the GUID assigned to the read in message
        
        # create error variables and assure they are cleared
        self.clearError()
        self.clearMsgFlags()
        
        # we need to set the include/exclues here
        self.callSetIncludeExcludeByDict(email_setting)
        
        # debugging
        # print('GmailImap:init:email_setting:', email_setting)
        
        # capture the debugging flag
        self.verbose = _setting_or_default('verbose', email_setting, None)

        # capture the imap library debugging - pass it into the library
        if 'imap_debug' in email_setting:
            imaplib.Debug = email_setting['imap_debug']

        # capture the imap_server or set a default
        self.imap_server = _setting_or_default('imap_server', email_setting, 'imap.gmail.com')
            
        # capture the folder we are reading from or set a default
        self.folder_read = quote_string_containing_spaces(_setting_or_default('imap_folder',email_setting,'inbox'))
            
        # capture the folder we are reading from or set a default
        self.folder_pass = quote_string_containing_spaces(_setting_or_default('imap_folder_pass',email_setting,None))

        # capture the folder we are reading from or set a default
        self.folder_fail = quote_string_containing_spaces(_setting_or_default('imap_folder_fail',email_setting,None))
            
        # fill in other settings that might have come in
        for setting in ('user','password'):
            self.__dict__[setting] = _setting_or_default(setting,email_setting,None)

        # capture the path to the root directory for saving message files
        self.msgPath = _setting_or_default('msgPath',email_setting,None)
            
        # create the imap object
        try:
            # debugging
            if self.verbose: print('GmailImap:init:create_imap_obj')
            # create an IMAP object
            self.imapobj = imaplib.IMAP4_SSL(self.imap_server)
        except Exception as e:
            self.error = e
            self.errmsg = 'init-exception:' + str(e)
            print('GmailImap:', self.errmsg)
            return None
        
        # test that we can create the message directory if passed in
        if self.msgPath:
            self.uidPath = _create_msg_dir( self.msgPath, '.test' )
            if self.uidPath:
                # remove the directory
                os.rmdir(self.uidPath)
                # kvutil.remove_dir(self.uidPath, 'kvgmailrcv:init')
                self.uidPath = None
                
        # if the user provided the user and password then login along with init
        if self.user and self.password:
            # debugging
            if self.verbose: print('GmailImap:init:login()')
            self.login()

        # if the user specified the folder we are going to - then move to that folder
        if self.loggedIn and self.folder_read:
            # debugging
            if self.verbose: print('GmailImap:select_folder:', self.folder_read)
            self.select_folder( )

    # clear previous processed errors
    def clearError(self):
        self.errmsg = ''
        self.error = None

    # clear flags and settings tied to getting a new message
    def clearMsgFlags(self):
        self.msgParsed = False
        self.msgProcessed = None
        self.msgSaved = False
        self.msgUID = None
        self.msgGUID = None
        self.uidPath = None

    # take a dict of many options - create a specific dict for calling the function
    def callSetIncludeExcludeByDict(self, optiondict={}):
        functionCallDict={}
        for mykey in ('fromIncludeEmails', 'fromIncludeDomains', 'fromExcludeIfNotInclude', 'fromExcludeEmails', 'fromExcludeDomains'):
            if mykey in optiondict and optiondict[mykey] is not None:
                functionCallDict[mykey] = optiondict[mykey]
            else:
                functionCallDict[mykey] = []
        # debugging
        # print('callSet:functionCallDict:', functionCallDict)
        # now call the function
        self.setIncludeExclude( **functionCallDict )
        
    # set up values for determining if we reject the email based on the from
    def setIncludeExclude(self, fromIncludeEmails=[], fromIncludeDomains=[], fromExcludeIfNotInclude=False, fromExcludeEmails=[], fromExcludeDomains=[]):
        self.fromIncludeEmails = []
        if isinstance(fromIncludeEmails, str):
            fromIncludeEmails=[fromIncludeEmails]
        for email in fromIncludeEmails:
            self.fromIncludeEmails.append(email.lower())
        self.fromIncludeDomains = []
        if isinstance(fromIncludeDomains, str):
            fromIncludeDomains=[fromIncludeDomains]
        for domain in fromIncludeDomains:
            self.fromIncludeDomains.append(domain.lower())
        self.fromExcludeIfNotInclude = fromExcludeIfNotInclude
        self.fromExcludeEmails = []
        if isinstance(fromExcludeEmails, str):
            fromExcludeEmails=[fromExcludeEmails]
        for email in fromExcludeEmails:
            self.fromExcludeEmails.append(email.lower())
        self.fromExcludeDomains = []
        if isinstance(fromExcludeDomains, str):
            fromExcludeDomains=[fromExcludeDomains]
        for domain in fromExcludeDomains:
            self.fromExcludeDomains.append(domain.lower())

    # routine takes the from address and determine if should exclude this message from processing
    def excludeMessage(self):
        lc_from = self.mparse.from_email.lower()
        (lc_user, lc_domain) = lc_from.split('@')
        if lc_from in self.fromIncludeEmails:
            return False
        if lc_domain in self.fromIncludeDomains:
            return False
        if self.fromExcludeIfNotInclude:
            return True
        if lc_from in self.fromExcludeEmails:
            return True
        if lc_domain in self.fromExcludeDomains:
            return True
        return False
        
    # login to an imap object
    def login(self, newuser=None, newpassword=None, newfolder=''):

        # set loggedin to false until we do log in
        self.loggedIn = False
        
        # check to see if the passed in information
        if newuser:
            # debugging
            if self.verbose: print('GmailImap:login:newuser:', newuser)
            self.user = newuser
        if newpassword:
            # debugging
            if self.verbose: print('GmailImap:login:newpassword:', newpassword)
            self.password = newpassword
        if newfolder:
            # debugging
            if self.verbose: print('GmailImap:login:newfolder:', newfolder)
            self.folder_read = quote_string_containing_spaces(newfolder)

        # now attempt to connect to login to the mail server
        try:
            # debugging
            if self.verbose: print('GmailImap:login')
            # login to the server with teh email/passwor
            rv, data = self.imapobj.login(self.user,self.password)
        except Exception as e:
            self.error = e
            self.errmsg = 'login-exception:' + str(e)
            if self.verbose:  print('GmailImap:', self.errmsg)
            return self.errmsg
    
        # validate we got logged in ok
        if rv != 'OK':
            self.error = None
            self.errmsg = 'login:Not able to sign in!'
            if self.verbose: print('GmailImap:login:errmsg:', self.errmsg)
            if self.verbose: print('GmailImap:login:data:', data)
            return self.errmsg

        # we have a valid login - set the flag
        self.loggedIn = True

        # clear any existing error
        self.clearError()
        
        # check to see if we have a folder to go to and go to it
        if self.folder_read:
            # debugging
            if self.verbose: print('GmailImap:login:select_folder:', self.folder_read)
            self.select_folder()

        # succeeded to pass back false (no error
        return False
        
    # select a folder for a logged in mail user
    def select_folder(self, newfolder=''):

        # set the current folder to None - which will reset to the folder selected later
        self.folder_current = None
        
        # if not logged in 
        if not self.loggedIn:
            # debugging
            if self.verbose: print('GmailImap:select_folder:not logged in')
            self.error = None
            self.errmsg = 'select_folder:must be logged in to select a folder'
            return self.errmsg
        
        # test to see if they passed in a new folder
        if newfolder:
            # debugging
            if self.verbose: print('GmailImap:select_folder:newfolder:', newfolder)
            self.folder_read = quote_string_containing_spaces(newfolder)
                  
        # now move to this folder
        try:
            # debugging
            if self.verbose: print('GmailImap:select_folder:set-folder-to:self.folder_read:', self.folder_read)
            rv, data = self.imapobj.select(self.folder_read)
            if rv != 'OK':
                self.error = None
                self.errmsg = 'select_folder:folder-selection-problem:' + str(data)
                if self.verbose: print('GmailImap:select_folder:errmsg:', self.errmsg)
                return self.errmsg
                
        except Exception as e:
            self.error = e
            if str(e) == "SELECT command error: BAD [b'Could not parse command']":
                self.errmsg = 'select_folder:could not select folder:' + self.folder_read
            else:
                self.errmsg = 'select_folder:Exception:' + str(e)
            if self.verbose: print('GmailImap:select_folder:', self.errmsg)
            return self.errmsg
        
        # capture the current folder - showing we are working on a folder
        self.folder_current = self.folder_read

        # debugging
        if self.verbose: print('GmailImap:select_folder:search_messages')
        # get the message list
        self.search_messages()

        
    # get the messages in the folder
    def search_messages(self):
        # clear any existing setting
        self.mail_ids = []
        
        #check to see if we have selected a folder - if not - we can not get the message list
        if not self.folder_current:
            self.error = None
            self.errmsg = 'search_messages: folder_current not set'
            if self.verbose:  print('GmailImap:', self.errmsg)
            return self.errmsg

        # now get the message list for this current folder
        try:
            # debugging
            if self.verbose: print('GmailImap:search_messages:uid(\'search\')')
            rv, data = self.imapobj.uid('search', None, "ALL") # search and return uids instead

            # debugging
            if self.verbose:
                print('GmailImap:search_messages:folder_current:', self.folder_current, "\nGmailImap:search_messages:rv:", rv, "\nGmailImap:search_messages:data:", data)
            
            # check to see we got an OK - there were messages found
            if rv != 'OK':
                self.error = None
                self.errmsg = 'search_message:selection-problem:' + str(data)
                print('GmailImap:search_messages:errmsg:', self.errmsg)
                return self.errmsg
        
            # the list of mail ids is the first thing that is returned, convert to ASCII if required
            self.mail_ids = data[0].decode('ASCII').split()

            # debugging
            if self.verbose: print('GmailImap:search_messages:mail_ids:', self.mail_ids)

        except Exception as e:
            self.error = e
            self.errmsg = 'search_messages:Exception:' + str(e)
            print('GmailImap:search_messages:Exception:', self.errmsg)
            return self.errmsg

    # pulls the oldest message off the list and processes it
    def getNextMessage(self):
        # clear any prior message
        self.clearMsgFlags()
        # debugging
        if self.verbose: print('GmailImap:getNextMessage:search_messages')
        # get the current list of messages
        self.search_messages()
        # if we got an error while searching -check the code and login again
        if self.errmsg: self.login()
            
        # debugging
        if self.verbose: print('GmailImap:getNextMessage:mail_ids:', self.mail_ids)

        # if there are messages
        if self.mail_ids:
            # debugging
            if self.verbose:  print('GmailImap:getNextMessage:mailID:', self.mail_ids[0])
            # set up other flags
            self.clearMsgFlags()
            # process the first one on this list
            self.mparse = get_imap_msg( self.imapobj, self.mail_ids[0] )
            # set the flag that we parsed this message
            self.msgParsed = True
            # debugging
            if self.verbose: print('GmailImap:getNextMessage:mparse:', self.mparse)
            if self.verbose: print('GmailImap:getNextMessage:mparse:type:', type(self.mparse))
            # dump_mparse(self.mparse)

        else:
            # return true because we did not perform the requested
            return True

    # pull a message - ass in the message id
    def getMessage(self, msgid):
        # set up other flags
        self.clearMsgFlags()
        # parse the message
        self.mparse = get_imap_msg( self.imapobj, msgid )
        # set the flag that we parsed this message
        self.msgParsed = True

    # save parsed message to file system
    def saveMessage(self):
        # if there is no parsed message OR
        # if the user did not set the directory path - there is nothing to save - i guess there should be an error?
        if not self.msgParsed or not self.msgPath:
            return False
        # create the path that this will save to
        self.uidPath = save_message(self.mparse, self.msgPath)
        # and set flag
        self.msgSaved = True

    # move the processed message to the appropriate folder (when defined)
    def moveProcessedMessage(self):
        # if no message was parsed nothing to do
        if not self.msgParsed:
            return False
        # if we have not processed this message - do nothing
        if self.msgProcessed == None:
            return False
        # now we have different things we can do
        if self.msgProcessed and self.folder_pass:
            # message was processed successfully so move it to the pass folder
            move_message(self.imap, self.mparse.msgUID, self.folder_pass)
        elif not self.msgProcessed and self.folder_fail:
            # message was processed successfully so move it to the pass folder
            move_message(self.imap, self.mparse.msgUID, self.folder_fail)
            
#------------------------------------------------------------

# exclude_from - list of email addresses to NOT process - run the not authorized
# include_from - list of email addresses to push through and process
#
# notify_msg_opt - dictionary of values required to send error messages
#   email_subject
#   email_to
#   email_cc

