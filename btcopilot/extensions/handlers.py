from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import logging
from logging.handlers import SMTPHandler
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonTracebackLexer
import smtplib


class ColorfulSMTPHandler(SMTPHandler):

    def getSubject(self, record):    
        return '[Family Diagram Server] ' + getattr(record, 'message', '')

    def emit(self, record):
        try:
            port = self.mailport
            if not port:
                port = smtplib.SMTP_PORT
            smtp = smtplib.SMTP(self.mailhost, port)
            msg = MIMEMultipart('alternative')
            msg['Subject'] = self.getSubject(record)
            msg['From'] = self.fromaddr
            msg['To'] = ",".join(self.toaddrs)
            msg['Date'] = formatdate()

            text = self.format(record)
            msg.attach(MIMEText(text, 'plain'))
            if record.exc_text:
                html_formatter = HtmlFormatter(noclasses=True)
                tb = highlight(record.exc_text, PythonTracebackLexer(), html_formatter)

                info = (self.formatter or logging._defaultFormatter)._fmt % record.__dict__
                info = '<p style="white-space: pre-wrap; word-wrap: break-word;">%s</p>' % info

                html = ('<html><head></head><body>%s%s</body></html>')% (info, tb)
                msg.attach(MIMEText(html, 'html'))
            if self.username:
                if self.secure is not None:
                    smtp.ehlo()
                    smtp.starttls(*self.secure)
                    smtp.ehlo()
                smtp.login(self.username, self.password)
            smtp.sendmail(self.fromaddr, self.toaddrs, msg.as_string())
            smtp.quit()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
