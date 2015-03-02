#!/usr/bin/python

import time
import os
import commands
import RPi.GPIO as GPIO
import json
import sys
import smtplib

from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


PARAMS = {
    u"tz": "America/Los_Angeles",
    u"time_sec": 15,
    u"resolution": "960x540",
    u"preview": 1,
    u"savedir": u"/home/pi/deer_camera/video",
    u"gpio_port": 21,
    u"open_box_limit_sec": 40,
    u"mail_movie": 0,
    u"send_mail": 0,
    }

def getLanIp(lan):
    (stat, out) = commands.getstatusoutput('ifconfig %s | grep "inet addr:" | cut -d : -f 2 | cut -d " " -f1' % lan)
    if stat or not out:
        return None
    else:
        return out

def sendMail(params, subject, message, attach=None):
    """Mail sending utility function."""
    lan_addr = getLanIp('wlan0')
    if not lan_addr:
       # lan_addr = getLanIp('eth0')
       if not lan_addr:
           print "Not connected to the network  - skipping mail"
           return

    from_addr = '%s@%s' % (params["smtp_user"], params["smtp_domain"])
    to_addr = params["alert_email"]
    message += "\n -- Sent from http://%s/" % lan_addr
    if attach is None:
        msg = MIMEText(message, 'plain')
    else:
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(message, 'plain'))
        for (mime_type, mime_subtype, name, bytes) in attach:
            payload = MIMEBase(mime_type, mime_subtype)
            payload.set_payload(bytes)
            encode_base64(payload)
            payload.add_header('Content-Disposition',
                               'attachment; filename="%s"' % name)
            msg.attach(payload)

    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr
    print "Sending to: ", params['smtp_server'], "/", params['smtp_port']
    smtp = smtplib.SMTP_SSL(params['smtp_server'],
                            params['smtp_port'])
    smtp.login(from_addr, params['smtp_pass'])
    smtp.sendmail(from_addr, [to_addr], msg.as_string())
    smtp.quit()
    print " === Mail sent to %s ==" % to_addr

def triggerOpenBox(p):
    print "Box is left open"
    if p['send_mail']:
        try:
            sendMail(p, "Mail Box Alert!", "Your Mailbox was left open - we disabled video recording. Please close it to restart video recording")
        except:
            print " -- Error sending email -- "

def triggerRecord(p):
    # if not p.get("smtp_pass", ""):
    #    p["smtp_pass"]  = getpass.getpass("Please enter your smtp user password :")

    n = p["gpio_port"]
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(n, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    off_time = 0
    box_left_open = False
    while True:
        state = GPIO.input(n)
        if not state:
            if not box_left_open:
                recordVideo(p)
            if time.time() - off_time > p["open_box_limit_sec"]: 
                if not box_left_open: 
                    triggerOpenBox(p)
                box_left_open = True
        else: 
            off_time = time.time()
            box_left_open = False
        time.sleep(0.1)
         

def recordVideo(p):
    t = time.localtime()
    cur_day = time.strftime("%Y_%m_%d", t)
    cur_time = time.strftime("%H_%M_%S", t)
    savedir = os.path.join(p["savedir"], cur_day)
    try:
        os.mkdir(savedir)
    except:
        pass

    sz = p['resolution'].split('x')
    width = int(sz[0])
    height = int(sz[1])
    preview = ""
    if p["preview"]:
        preview = "-p 0,150,%s,%s" % (width, height)
    
    h264_file = "%s/%s.h264" % (savedir, cur_time)
    movie_file = "%s/%s.mp4" % (savedir, cur_time)
    image_file = "%s/%s.jpeg" % (savedir, cur_time)
   
    # record video from the camera as in instructed by 
    # our parameters 
    cmd = "raspivid -w %s -h %s -t %s -o %s %s" % (
        width, height, p["time_sec"]*1000,
        h264_file, preview)    

    print cmd
    (stat, out) = commands.getstatusoutput(cmd)
    print "%s / %s" % (stat, out)
    if stat != 0:
        return
   
    # make the recorded file an mp4
    cmd = "MP4Box -fps 30 -add %s %s" % (h264_file, movie_file)
    print cmd
    (stat, out) = commands.getstatusoutput(cmd)
    print "%s / %s" % (stat, out)
    if stat != 0:
        return

    # get a frame as an image file
    cmd = "ffmpeg -i %s -ss 0.5 -vframes 1 -f image2 %s" % (movie_file, image_file)
    print cmd
    (stat, out) = commands.getstatusoutput(cmd)
    print "%s / %s" % (stat, out)
    if stat != 0:
        return

    os.unlink(h264_file)
    if not p["send_mail"]:
        return
    try:
        content = None
        if p["mail_movie"]:
            with open(movie_file) as f:
                content = [('video', 'mpeg', movie_file, f.read())]
        else:
            with open(image_file) as f:
                content =  [('image', 'jpeg', image_file, f.read())]

        sendMail(p, "Mail Box Alert!", "Your Mailbox was Opened!", content)
    except:
        print " -- Cannot send mail -- "

def loadParams():
    config = json.loads(open(sys.argv[1]).read()) 
    global PARAMS
    PARAMS.update(config)
    os.environ['TZ'] = config.get('tz', 'America/Los_Angeles')
    time.tzset()

if __name__ == "__main__":
    loadParams()
    # except: pass
    triggerRecord(PARAMS)
