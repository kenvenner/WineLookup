'''
@author:   Ken Venner
@contact:  ken@venerllc.com
@version:  1.03

Library of tools used send out message through gmail
'''

from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mimetypes
import os
import re
import smtplib
import sys

# logging
import logging

logger = logging.getLogger(__name__)

# version number
AppVersion = '1.03'


class GmailSend:
    """
    This class handles the creation and sending of email messages
    via SMTP.  This class also handles attachments and can send
    HTML messages.  The code comes from various places around
    the net and from my own brain.
    """

    def __init__(self, sendfrom: str, sendpass: str):
        """
        Create a new empty email sending message object.

        @param sendfrom: the email address of the account being used to send the email
        @type smtpServer: String
 
        @param sendpass: the password of the account being used to send the email
        @type smtpServer: String
        """
        self._reEmail = re.compile(
            "^([\\w \\._]+\\<[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\\>|[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)$")

        if not self.validateEmailAddress(sendfrom):
            raise Exception("Invalid email address '%s'" % sendfrom)
        self._sendfrom = sendfrom
        self._sendpass = sendpass
        self._from = sendfrom
        self._replyto = None
        self._textBody = None
        self._htmlBody = None
        self._subject = ""
        self.clearRecipients()
        self.clearAttachments()

    def send(self):
        """
        Send the email message represented by this object.
        """
        # Validate message
        if self._textBody is None and self._htmlBody is None:
            raise Exception("Error! Must specify at least one body type (HTML or Text)")
        if len(self._to) + len(self._cc) + len(self._bcc) == 0:
            raise Exception("Must specify at least one recipient (to,cc,bcc)")

        # Create the message part
        if self._textBody is not None and self._htmlBody is None:
            msg = MIMEText(self._textBody, "plain")
        elif self._textBody is None and self._htmlBody is not None:
            msg = MIMEText(self._htmlBody, "html")
        else:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(self._textBody, "plain"))
            msg.attach(MIMEText(self._htmlBody, "html"))
        # Add attachments, if any
        if len(self._attach) != 0:
            tmpmsg = msg
            msg = MIMEMultipart()
            msg.attach(tmpmsg)
        for fname, attachname in self._attach:
            if not os.path.exists(fname):
                print("File '%s' does not exist.  Not attaching to email." % fname)
                continue
            if not os.path.isfile(fname):
                print("Attachment '%s' is not a file.  Not attaching to email." % fname)
                continue
            # Guess at encoding type
            ctype, encoding = mimetypes.guess_type(fname)
            if ctype is None or encoding is not None:
                # No guess could be made so use a binary type.
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            if maintype == 'text':
                fp = open(fname)
                attach = MIMEText(fp.read(), _subtype=subtype)
                fp.close()
            elif maintype == 'image':
                fp = open(fname, 'rb')
                attach = MIMEImage(fp.read(), _subtype=subtype)
                fp.close()
            elif maintype == 'audio':
                fp = open(fname, 'rb')
                attach = MIMEAudio(fp.read(), _subtype=subtype)
                fp.close()
            else:
                fp = open(fname, 'rb')
                attach = MIMEBase(maintype, subtype)
                attach.set_payload(fp.read())
                fp.close()
                # Encode the payload using Base64
                encoders.encode_base64(attach)
            # Set the filename parameter
            if attachname is None:
                filename = os.path.basename(fname)
            else:
                filename = attachname
            attach.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(attach)
        # Some header stuff
        msg['Subject'] = self._subject
        msg['From'] = self._from
        if self._replyto:
            msg['Reply-to'] = self._replyto
        # address prep
        sendtolist = []
        if self._to:
            msg['To'] = ", ".join(self._to)
            sendtolist.extend(self._to)
        if self._cc:
            msg['Cc'] = ", ".join(self._cc)
            sendtolist.extend(self._cc)
        if self._bcc:
            sendtolist.extend(self._bcc)
        msg.preamble = "You need a MIME enabled mail reader to see this message"
        # Send message
        smtp = smtplib.SMTP(host="smtp.gmail.com", port=587)
        smtp.ehlo()
        smtp.starttls()
        smtp.login(self._sendfrom, self._sendpass)
        smtp.ehlo()
        smtp.sendmail(self._sendfrom, sendtolist, msg.as_string())
        smtp.close()

    def setSubject(self, subject):
        """
        Set the subject of the email message.
        """
        self._subject = subject

    def setFrom(self, address):
        """
        Set the message header for email sender (defaults to 'sendfrom').
        """
        if not self.validateEmailAddress(address):
            raise Exception("Invalid email address '%s'" % address)
        self._from = address

    def setReplyTo(self, address):
        """
        Set the email message reply to email address.
        """
        if not self.validateEmailAddress(address):
            raise Exception("Invalid email address '%s'" % address)
        self._replyto = address

    def clearRecipients(self, addrtype=None):
        """
        Remove all currently defined recipients for
        the email message, if addrtype is not set.

        @param addrtype: the recipient type to be cleared (to,cc,bcc)
        @type smtpServer: String
        """
        if addrtype is None or addrtype.lower() == 'to':
            self._to = []
        if addrtype is None or addrtype.lower() == 'cc':
            self._cc = []
        if addrtype is None or addrtype.lower() == 'bcc':
            self._bcc = []

    def addRecipient(self, address: str, addrtype='to'):
        """
        Add a new recipient to the email message.
        Add to the 'to' field unless addrtype parameter is set

        @param addrtype: the recipient type to be cleared (to,cc,bcc)
        @type smtpServer: String
        """
        if not self.validateEmailAddress(address):
            raise Exception("Invalid email address '%s'" % address)
        if addrtype.lower() == 'to':
            self._to.append(address)
        elif addrtype.lower() == 'cc':
            self._cc.append(address)
        else:
            self._bcc.append(address)

    def addRecipients(self, addresses: list, addrtype='to'):
        """
        Add a list new recipient to the email message.
        Add to the 'to' field unless addrtype parameter is set

        @param addrtype: the recipient type to be cleared (to,cc,bcc)
        @type smtpServer: String
        """
        for address in addresses:
            self.addRecipient(address, addrtype)

    def setTextBody(self, body):
        """
        Set the plain text body of the email message.
        """
        self._textBody = body

    def setHtmlBody(self, body):
        """
        Set the HTML portion of the email message.
        """
        self._htmlBody = body

    def clearBody(self, type=None):
        """
        Clear the email message body

        Clear both html and plain unless parameter is specified

        @param type: the body type to be cleared (text, plain, html )
        @type smtpServer: String
        """
        if type is None or type.lower() == 'text' or type.lower() == 'plain':
            self._textBody = None
        if type is None or type.lower() == 'html':
            self._htmlBody = None

    def clearAttachments(self):
        """
        Remove all file attachments.
        """
        self._attach = []

    def addAttachment(self, fname: str, attachname=None):
        """
        Add a file attachment to this email message.

        @param fname: The full path and file name of the file
                      to attach.
        @type fname: String
        @param attachname: This will be the name of the file in
                           the email message if set.  If not set
                           then the filename will be taken from
                           the fname parameter above.
        @type attachname: String
        """
        if fname is None:
            return
        self._attach.append((fname, attachname))

    def validateEmailAddress(self, address: str):
        """
        Validate the specified email address.
        
        @return: True if valid, False otherwise
        @rtype: Boolean
        """
        if self._reEmail.search(address) is None:
            return False
        return True


if __name__ == "__main__":
    # Run some tests
    import kvutil

    optiondict = kvutil.kv_parse_command_line(
        {"email_user": {}, "email_password": {}, "conf_json": {"value": "gmail-wines.json"}}, debug=False)
    fromaddr = optiondict['email_user']
    password = optiondict['email_password']
    mFrom = "Test User <test@mydomain.com>"
    mTo = "ken@vennerllc.com"

    # create the sending mail object
    m = GmailSend(fromaddr, password)
    m.addRecipient(mTo)

    # Simple Plain Text Email
    m.setSubject("Plain text email")
    m.setTextBody("This is a plain text email <b>I should not be bold</b>")
    m.send()

    # Plain text + attachment
    m.setSubject("Text plus attachment")
    m.addAttachment('winetodayattune.csv')
    m.send()

    # Simple HTML Email
    m.clearAttachments()
    m.clearBody()
    m.setSubject("HTML Email")
    m.setHtmlBody("The following should be <b>bold</b>")
    m.send()

    # HTML + attachment
    m.setSubject("HTML plus attachment")
    m.addAttachment('winetodayattune.csv')
    m.send()

    # Text + HTML
    m.clearAttachments()
    m.clearBody()
    m.setSubject("Text and HTML Message")
    m.setTextBody("You should not see this text in a MIME aware reader")
    m.setHtmlBody("The following should be <b>bold</b>")
    m.send()

    # Text + HTML + attachment
    m.setSubject("HTML + Text + attachment")
    m.addAttachment('winetodayattune.csv')
    m.send()

    # Text + HTML + attachments
    m.setSubject("HTML + Text + attachments (csv + xlsx)")
    m.addAttachment('winetodayattune.xlsx')
    m.send()

    # Simple Text CC only Email
    m.clearAttachments()
    m.clearRecipients()
    m.clearBody()
    m.addRecipient(mTo, 'cc')
    m.setSubject("Text Email + Cc Only")
    m.setTextBody("This is a plain text email <b>I should not be bold</b>")
    m.send()

    # Simple Text BCC only Email
    m.clearAttachments()
    m.clearRecipients()
    m.clearBody()
    m.addRecipient(mTo, 'bcc')
    m.setSubject("Text Email + Bcc Only")
    m.setTextBody("This is a plain text email <b>I should not be bold</b>")
    m.send()

    # Simple Text BCC only Email
    m.clearAttachments()
    m.clearRecipients()
    m.clearBody()
    m.addRecipient(mTo)
    m.setReplyTo('ken_venner@yahoo.com')
    m.setSubject("Text Email + ReplyTo")
    m.setTextBody("This is a plain text email <b>I should not be bold</b>")
    m.send()

# eof
