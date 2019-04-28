'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.23

Tool used to create an email watcher and process inbound emails
and return back a list of wines that match the subject
'''

import kvgmailrcv
import kvgmailsend
import kvutil

import datetime
import imaplib
import sys
import re

import wineutil

import time

# Logging Setup
import os
import logging
# logging.basicConfig(level=logging.INFO)
logging.basicConfig(filename=os.path.splitext(os.path.basename(__file__))[0]+'.log',
                    level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(threadName)s -  %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# application variables
optiondictconfig = {
    'AppVersion' : {
        'value' : '1.23',
        'description' : 'defines the version number for the app',
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
    'sleepseconds' : {
        'value' : 60,
        'type' : 'int',
        'description' : 'defines the number of seconds to sleep between runs',
    },
}


### GLOBAL VARIABLES ####

# regex that looks for the word undeliverable in the subject
reUndeliverable = re.compile(r'undeliverable', re.IGNORECASE)

# mail errors
mailerrors = [
    'command: SELECT => socket error: EOF',
    'command: SELECT => System Error',
    'command: SELECT => Session expired, please login again.',
    'socket error: [WinError 10053] An established connection was aborted by the software in your host machine',
    '[WinError 10060] A connection attempt failed because the connected party did not properly respond after a period of time, or established connection failed because connected host has failed to respond',
]


# settings used to drive this test case
base_email_settings = {
    'imap_server' : 'imap.gmail.com',
    'imap_port'   : 993,
    'imap_folder' : 'inbox',
    'user'        : 'wines@vennerllc.com',
    'password'    : 'win3s3arch*',
}

# # routine that will continously monitor a mail box and process messages
# 1) Open mail parser to the mail box
# 2) In a loop - that checks every XX seconds (done when we don't find messages) - otherwise keep looping
# 3) check for messages (get list of messages waiting)
#    a) if no message sleep the define time - loop again
#    b) pull the oldest message from the queue
#    c) parse the message
#    d) parse out the from, and cc and build the outbound to and cc fields
#    e) create an outbound email client using creds for inbound
#    f) add to/cc recipients
#    g) add subject
#    h) add HtmlBody by parsing subject to get full wine string (srch_full)
#    i) send out email that was created
#    j) if all above worked - move processed file to 'Processed'
#
def gmail_poll_by_function(base_email_settings, winesel_storelist, wine2_storelist, sleepseconds, debug=False):
    # debug
    if debug: print('init-gmailrcv')
    
    # create the IMAP object
    mail = kvgmailrcv.init( base_email_settings )

    # this should be a do while True statement but we are testing
    #for i in range(30):
    while True:
        # debugging
        if debug:
            print('select_folder:', base_email_settings['imap_folder'])
        
        # get the message
        try:
            mailids = kvgmailrcv.select_folder(mail, base_email_settings['imap_folder'])
        except Exception as e:
            logger.warning('select_folder:failed:')
            logger.warning('str(e):%s', str(e))
            logger.warning('type(e):%s', type(e))
            logger.warning('e.args:%s', e.args)
            if isinstance(e, imaplib.IMAP4.abort):
                if str(e) in mailerrors:
                    logger.warning('rebuild the mail object by calling  kvgmailrcv.init')
                    mail = kvgmailrcv.init( base_email_settings )
                else:
                    logger.error('terminating application')
                    # restart the mail receiving object
                    sys.exit(1)
            else:
                logger.error('terminating application')
                # restart the mail receiving object
                sys.exit(1)

        # action if we found a record
        if mailids:
            # set the flag
            msgProcessed = True
            
            # grab the oldest message to process first
            msgid = mailids[0]

            # get the imap object
            mparse = kvgmailrcv.get_imap_msg(mail, msgid)

            # print the subject
            logger.info('msgid:%s:subject:%s', msgid, mparse.subject)
            logger.info('from:%s', mparse.from_email)
            
            # process this email message
            try:
                # setup the email sender
                m = kvgmailsend.GmailSend(base_email_settings['user'], base_email_settings['password'])
                # check if undeliverable is in the subject
                if reUndeliverable.search(mparse.subject):
                    logger.info('Undeliverable in the subject - skippping this message')
                else:
                    logger.info('Processing email subject:%s', mparse.subject)
                    m.addRecipients(mparse.from_email)
                    if mparse.cc_mail:
                        m.addRecipients(mparse.cc_email, 'cc')
                    m.setSubject('WineLookup:' + mparse.subject)
                    # get the message body by doing the message lookup
                    m.setHtmlBody(wineutil.html_body_from_email_subject(mparse.subject, winesel_storelist, winereq_storelist))
                    m.send()
                    logger.info('response emailed')
            except Exception as e:
                logger.error('Failed to process msg[%s]-error:%s', msgid,str(e))
                msgProcessed = False
                # i think we need to fail here rather than continue to loop
                sys.exit(1)

            # finally delete this message
            if msgProcessed:
                logger.info('moving message to folder:Processed')
                kvgmailrcv.move_message(mail, msgid, 'Processed')
        else:
            logger.info('Sleeping %d seconds - and checking again', sleepseconds)
            time.sleep(sleepseconds)


if __name__ == '__main__':

    # capture the command line
    optiondict = kvutil.kv_parse_command_line( optiondictconfig, debug=False )

    # (wineselenium) selenium stores
    winesel_storelist = [
        'bevmo',
        'hitime',
        'pavillions',
        'totalwine',
        'wineclub',
        'wally',
    ]

    # (winerequest) request stores
    winereq_storelist = [
        'winex',
        'napacab',
        'webwine',
        'wineconn',
        'johnpete',
        'klwine',
        'nhliquor',
    ]

    # call the routine and get into the never ending loop
    gmail_poll_by_function(base_email_settings, winesel_storelist, winereq_storelist, optiondict['sleepseconds'], debug=optiondict['debug'])

#eof
