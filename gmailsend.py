'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.01

Command line gmail mail sending tool

'''

import kvutil
import kvgmailsend

import time
import re
import datetime
import sys
from socket import gethostname


# logging - 
import kvlogger
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
        'value' : '1.01',
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
    'email_user' : {
        'value' : 'wines@vennerllc.com',
        'description' : 'defines the mail account we are sending from',
    },
    'email_password' : {
        'value' : None,
        'description' : 'defines the password for the mail account',
    },
    'email_type' : {
        'value' : 'text',
        'description' : 'defines the email type (text or html)',
    },
    'email_replyto' : {
        'value' : 'wines@vennerllc.com',
        'description' : 'defines the email that we will reply to',
    },
    'email_from' : {
        'value' : 'wines@vennerllc.com',
        'description' : 'defines who the email appears to be from',
    },
    'email_to' : {
        'value' : ['ken@vennerllc.com'],
        'type'  : 'liststr',
        'description' : 'defines the list of email accounts we send to',
    },
    'email_cc' : {
        'value' : None,
        'type'  : 'liststr',
        'description' : 'defines the list of email accounts we cc send to',
    },
    'email_subject' : {
        'value' : None,
        'description' : 'defines the subject line of the email generated',
    },
    'email_subject_adder' : {
        'value' : None,
        'description' : 'defines added text to the subject line of the email generated',
    },
    'email_subject_addtime' : {
        'value' : True,
        'type'  : 'bool',
        'description' : 'defines if we add time to subject line',
    },
    'email_message' : {
        'value' : None,
        'description' : 'defines the body of the message on command line',
    },
    'email_message_file' : {
        'value' : None,
        'description' : 'defines the body of the message via a file to be imported',
    },
    'email_attachments' : {
        'value' : [],
        'type'  : 'liststr',
        'description' : 'defines the list of attachment files to be added to this message',
    },
    'email_server' : {
        'value' : 'imap.gmail.com',
        'description' : 'defines the dns for mail server',
    },
    'email_port'   : {
        'value' : 993,
        'description' : 'defines the port for the mail server',
    },
}


def validate_optiondict( optiondict, debug=False ):
    foundError = []
    
    # must set all these variables
    for fld in ('email_user','email_password', 'email_replyto'):
        if not( fld in optiondict and  optiondict[fld] ):
            logger.error('option is not set:%s', fld)
            foundError.append(fld)

    if foundError:
        raise Exception('missing definitions:{}'.format(','.join(foundError)))

    # must set one of these two variables
    for fld in ('email_to', 'email_cc'):
        if not fld in optiondict and not optiondict[fld]:
            foundError.append(fld)
    if len(foundError) > 1:
        logger.error('please set one of these options:%s', ','.join(foundError))
        raise Exception('please set one of these options:{}'.format( ','.join(foundError)))
    foundError = []

    # check to see if filenames provided exist - email_message_file
    for fld in ('email_message_file'):
        if fld in optiondict and optiondict[fld] and not os.path.exists(optiondict[fld]):
            logger.error('%s file does not exist:%s', fld, optiondict[fld])
            raise Exception('{} file does not exist:{}'.format( fld, optiondict[fld]) )

    # check to see if filenames provided exist - email_attachments
    for fld in ('email_attachments'):
        if fld in optiondict and optiondict[fld]:
            for file in optiondict[fld]:
                if not os.path.exists(file):
                    logger.error('%s file does not exist:%s', fld, file)
                    foundError.append(fld)

            if foundError:
                raise Exception('{} file does not exist:{}'.format( fld, ','.join(foundError)))

        
def generate_subject( optiondict, debug=False ):
    subject = ''
    if optiondict['email_subject']:
        subject += optiondict['email_subject']
    if optiondict['email_subject_addtime']:
        if subject[-1] != ' ':
            subject += ' '
        subject += str(datetime.datetime.now())
    if optiondict['email_subject_adder']:
        subject += optiondict['email_subject_adder']

    return subject



# ---------------------------------------------------------------------------
if __name__ == '__main__':

    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    # validate the command line
    validate_optiondict( optiondict, debug=False )

    
    # create email object
    m = kvgmailsend.GmailSend(optiondict['email_user'], optiondict['email_password'])

    # set who it is going to
    if optiondict['email_to']:
        m.addRecipients(optiondict['email_to'])
    if optiondict['email_cc']:
        m.addRecipients(optiondict['email_cc'], 'cc')

    # set the subject
    m.setSubject(generate_subject(optiondict))

    # set the message body
    if optiondict['email_message_file']:
        body = kvutil.slurp(optiondict['email_message_file'])
    elif optiondict['email_message']:
        body = optiondict['email_message']
    else:
        body = None

    if body:
        if optiondict['email_type'].upper() == 'HTML':
            m.setHtmlBody(body)
        else:
            m.setTextBody(body)

    # add attachments
    for attachment in optiondict['email_attachments']:
        m.addAttachment(attachment)

    # send out this message
    m.send()
    
    
