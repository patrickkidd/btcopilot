from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import itertools
import logging
from logging.handlers import SMTPHandler
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonTracebackLexer
from pathlib import Path
import smtplib
import sys

from celery import current_task
from flask import has_request_context, request

import btcopilot


class ColorfulSMTPHandler(SMTPHandler):

    def origin(self):
        return f"{self.source()} {btcopilot.__version__}"

    def source(self):
        if has_request_context():
            return f"Server: {request.host}{request.path}"
        if current_task:
            return f"Server: worker {current_task.name}"
        program, args = sys.argv[0], sys.argv[1:]
        name = Path(program).name
        if name == "gunicorn":
            return "Server: gunicorn"
        if "celery" in Path(program).parts:
            return " ".join(["Server: celery", *(a for a in args if a in ("worker", "beat"))])
        if name in ("flask", "alembic"):
            words = list(itertools.takewhile(lambda a: not a.startswith("-"), args))
            return f"Script: {' '.join(words if name == 'flask' else [name, *words])}"
        if program in ("", "-"):
            return "Script: python"
        if program == "-c":
            return "Script: python -c"
        return f"Script: {name}"

    def getSubject(self, record):
        return f"[{self.origin()}] " + record.getMessage()

    def format(self, record):
        return f"{self.origin()}\n" + super().format(record)

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
