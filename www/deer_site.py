#!/usr/bin/python

import web
import time
import glob
import os
import sys
import json
import commands

config_file = '/home/pi/deer_camera/cfg/deer.cfg'

urls = (
    '/videolist', 'videolist',
    '/config', 'configurator',
    '/restart', 'restarter',
)
url_prefix = '/video/'
videodir = '/home/pi/deer_camera/video/'
t_globals = dict(
)

render = web.template.render('/home/pi/deer_camera/www/templates/', cache=False,  globals=t_globals)

def getVideoFiles(uri_prefix, video_dir):
    thumbs = glob.glob(videodir + "/2*/*.jpeg")
    thumbs.sort()
    thumbs.reverse()
    videos = []
    for t in thumbs:
        jpeg_fn = os.path.basename(os.path.dirname(t)) + "/" + os.path.basename(t)
        mp4_fn = jpeg_fn[:-4] + "mp4"
        tspec = time.strptime(jpeg_fn, "%Y_%m_%d/%H_%M_%S.jpeg")
        videos.append( (time.asctime(tspec), uri_prefix + jpeg_fn, uri_prefix + mp4_fn, jpeg_fn[:-4]) )
    return videos

class videolist:
    def GET(self):
        videos = getVideoFiles(url_prefix, videodir)
        videolist = '\n'.join(unicode(render.videocell(t[0], t[1], t[2], t[3])) for t in videos)
        return render.videolist(renderer=render, videolist=videolist)

    def POST(self):
        delroot =  GetStringParam('delroot', None)
        if delroot:
            pattern = videodir + "/" + delroot + "*"
            files = glob.glob(pattern)
            for f in files:
                print " Deleting file :", f
                try:
                    os.unlink(f)
                except:
                    pass
        return self.GET()

def GetStringParam(name, default=None):
    param = web.input()
    if param.has_key(name):
        return param.get(name)
    return default

def GetIntParam(name, default=0):
    param = web.input()
    if not param.has_key(name):
        return default
    try:
        return int(param.get(name))
    except ValueError, e:
        return default

def GetWlanEssid():
    (stat, out) = commands.getstatusoutput('iwconfig 2>/dev/null | grep ESSID | cut -d \'"\' -f 2')
    print "Essid: %s / %s" % (stat, out)
    if stat or not out:
        return None
    else:
        return out

def GetWlanIp():
    (stat, out) = commands.getstatusoutput('ifconfig wlan0 | grep "inet addr:" | cut -d : -f 2 | cut -d " " -f1')
    print "wlanip: %s / %s" % (stat, out)
    if stat or not out:
        return None
    else:
        return out

class restarter:
    def GET(self):
        with open(config_file) as f:
            config = json.loads(f.read())
        config['wlan_network'] = GetWlanEssid()
        return render.configure(renderer=render, config=config, wlan_ip=GetWlanIp())

    def POST(self):
        (stat, out) = commands.getstatusoutput('reboot')
        print "Reboot: %s/ %s" % (stat, out)
        return render.restart()

class configurator:
    def GET(self):
        with open(config_file) as f:
            config = json.loads(f.read())
        config['wlan_network'] = GetWlanEssid()
        return render.configure(renderer=render, config=config, wlan_ip=GetWlanIp())

    def POST(self):
        error = []
        
        with open(config_file) as f:
            config = json.loads(f.read())

        config['resolution'] =  GetStringParam('size_select', config['resolution'])
        time_sec = GetIntParam('timesec', config['time_sec'])
        if time_sec < 5:
            error.append('Recording time to short')
        else:
            config['time_sec'] = time_sec

        config['open_timespec'] = GetIntParam('open_timesec', config['open_box_limit_sec'])
        if (config['open_timespec'] < config['time_sec']):
            error.append('Open time too short')
            config['open_timespec'] = 2 * config['time_sec']
            
        send_mail = GetIntParam('send_mail', 0)
        if send_mail: config['send_mail'] = 0
        else: config['send_mail'] = 1

        smtp_email = GetStringParam('smtp_email', config['smtp_user'] + '@' + config['smtp_domain'])
        comp = smtp_email.split('@')
        if len(comp) == 2:
            config['smtp_user'] = comp[0]
            config['smtp_domain'] = comp[1]
        elif config['send_mail']:
            error.append('Invalid sender email address')

        smtp_server = GetStringParam('smtp_server', '%s:%s' % (config['smtp_server'], config['smtp_port']))
        comp = smtp_server.split(':')
        if len(comp) == 2:
            config['smtp_server'] = comp[0]
            try:
                config['smtp_port'] = int(comp[1])
            except:
                error.append('Invalid smtp server')
        else:
            config['smtp_server'] = smtp_server

        smtp_pass = GetStringParam('smtp_pass', '')
        if smtp_pass and smtp_pass != 'pass_set':
            config['smtp_pass'] = smtp_pass

        alert_email = GetStringParam('alert_email', config['alert_email'])
        comp = smtp_email.split('@')
        if len(comp) == 2:
            config['alert_email'] = alert_email
        elif config['send_mail']:
            error.append('Invalid alert email address')

        mail_movie = GetStringParam('mail_movie', 'jpg')
        if mail_movie == 'mpg':
            config['mail_movie'] = 1
        else:
            config['mail_movie'] = 0

        try:
            with open(config_file + '_', 'w') as f:            
                f.write(json.dumps(config))
            os.rename(config_file + '_', config_file)
        except:
            error.append('Error saving the configuration')

        (stat, out) = commands.getstatusoutput('restart deer')
        print "Restart - %s / %s" % (stat, out)
        if stat:
            error.append('Error restarting the monitoring service.')

        wlan_net = GetStringParam('wlan_network', '')
        wlan_pass = GetStringParam('wlan_pass', '')
        restart = False
        if wlan_net and wlan_pass and wlan_pass != 'pass_set':
            with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'a') as wpa:
                wpa.write("\nnetwork={\n  ssid=\"%s\"\n  psk=\"%s\"\n}\n" % (wlan_net, wlan_pass));
                restart = True

        config['wlan_network'] = GetWlanEssid()

        return render.configure(renderer=render, config=config, wlan_ip=GetWlanIp(), error='\n'.join(error), restart=restart)
        


if __name__ == "__main__":
    app = web.application(urls, globals())
    app.internalerror = web.debugerror
    app.run()
