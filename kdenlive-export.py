#!/usr/bin/env python3

import xmltodict
import json
import re
import glob
import os
import subprocess
import sys
import svgutils

def get_datapoints(event):
    return list([(float(x)/100, float(y)/100) for x, y in re.findall(r'([^,]+),([^,]+)', event['dataPoints'])])

def annot_pencil(event, res):
    width,height = res
    svg = '<path stroke="#%06x" fill="none" stroke-linejoin="round" stroke-linecap="round" stroke-width="%.2f" d="' % (int(event['color']), (float(event['thickness'])/100*width))
    datapoints = get_datapoints(event)
    for c in event['commands'].split(","):
        if c == "1":
            x, y = datapoints.pop(0)
            svg += 'M%s, %s ' % (x*width, y*height)
        elif c == "2":
            x, y = datapoints.pop(0)
            svg += 'L%s, %s ' % (x*width, y*height)
        elif c == "3":
            x1, y1 = datapoints.pop(0)
            x2, y2 = datapoints.pop(0)
            svg += 'Q%s, %s, %s, %s ' % (x1*width, y1*height, x2*width, y2*height)
        elif c == "4":
            x1, y1 = datapoints.pop(0)
            x2, y2 = datapoints.pop(0)
            x3, y3 = datapoints.pop(0)
            svg += 'C%s, %s, %s, %s, %s, %s ' % (x1*width, y1*height, x2*width, y2*height, x3*width, y3*height)
    svg += '"/>'
    return svg

def annot_line(event, res):
    width,height = res
    event["commands"] = "1,2"
    return annot_pencil(event)

def annot_ellipse(event, res):
    width,height = res
    datapoints = get_datapoints(event)
    x1, y1 = datapoints[0]
    x2, y2 = datapoints[1]
    rx = (x2 - x1) / 2
    ry = (y2 - y1) / 2
    cx = ((rx + x1) * width)
    cy = ((ry + y1) * height)
    rx = abs(rx * width)
    ry = abs(ry * height)
    svg = '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="none" stroke="#%06x" stroke-width="%s" />' % (cx, cy, rx, ry, int(event['color']), float(event['thickness'])/100*width)
    return svg

def annot_rectangle(event, res):
    width,height = res
    datapoints = get_datapoints(event)
    x1, y1 = datapoints[0]
    x2, y2 = datapoints[1]

    if x2 < x1:
        x1 = datapoints[1][0]
        x2 = datapoints[0][0]

    if y2 < y1:
        y1 = datapoints[1][1]
        y2 = datapoints[0][1]

    svg = '<rect x="%s" y="%s" width="%s" height="%s" fill="none" stroke="#%06x" stroke-width="%s" />' % (x1 * width, y1 * height, (x2-x1)*width, (y2-y1)*height, int(event['color']), float(event['thickness'])/100*width)
    return svg

def annot_triangle(event, res):
    width,height = res
    datapoints = get_datapoints(event)
    print(datapoints)
    xBottomLeft, yTop = datapoints[0]
    xBottomRight, yBottomLeft = datapoints[1]
    yBottomRight = yBottomLeft
    xTop = (xBottomRight - xBottomLeft)/2 + xBottomLeft

    d = "M%s, %s, %s, %s, %s, %s Z" % (xTop*width, yTop*height, xBottomLeft*width, yBottomLeft*height, xBottomRight*width, yBottomRight*height)

    svg = '<path d="%s" fill="none" stroke="#%06x" stroke-width="%s" />' % (d, int(event['color']), float(event['thickness'])/100*width)
    return svg

def annot_text(event, res):
    width,height = res
    if event["textBoxWidth"] == "0":
        return ""

    if event["text"] is None:
        return ""

    datapoints = get_datapoints(event)
    x, y = datapoints[0]

    textboxwidth = float(event["textBoxWidth"])/100 * width
    textboxheight = float(event["textBoxHeight"])/100 * height

    svg = '<text x="%s" y="%s" width="%s" height="%s" font-family="Arial" font-size="%s" fill="#%06x">' % (float(event['x'])/100*width, float(event['y'])/100*height, textboxwidth, textboxheight, float(event['calcedFontSize'])/100*height, int(event['fontColor']))
    svg += event['text']
    svg += '</text>'
    return svg


# throw into raw recording directory next to events.xml and run, should generate out/*.pdf
path = sys.argv[1]
os.chdir(path)
if not os.path.exists("frames"):
    os.mkdir("frames")

recording = xmltodict.parse(open("events.xml").read())['recording']

IGNORE_EVENTS = [
    'WhiteboardCursorMoveEvent',
    'AssignPresenterEvent',
    'ConversionCompletedEvent',
#    'CreatePresentationPodEvent',
#    'EndAndKickAllEvent',
    'ParticipantJoinedEvent',
#    'ParticipantJoinEvent',
    'SetPresentationDownloadable',
    'SetPresenterInPodEvent',
#    'StartRecordingEvent',
#    'SharePresentationEvent',
    'ResizeAndMoveSlideEvent',
#    'GotoSlideEvent',
    'ParticipantLeftEvent',
    'ParticipantMutedEvent',
    'DeskShareStartRTMP',
    'DeskShareStopRTMP',
    'ParticipantStatusChangeEvent',
    'ParticipantTalkingEvent',
    'PublicChatEvent',
    'RecordStatusEvent',
#    'StartWebRTCDesktopShareEvent',
#    'StartWebRTCShareEvent',
#    'StopWebRTCDesktopShareEvent',
#    'StopWebRTCShareEvent',
]

presentations = {}

def render(slide):
    width = float(slide['origsvg'].split('width="')[1].split('"')[0].replace('pt', ''))
    height = float(slide['origsvg'].split('height="')[1].split('"')[0].replace('pt', ''))

    svg = slide['origsvg'].replace('</svg>', '')

    for shapeid, event in slide['drawings'].items():
        if event["type"] == "pencil":
            svg += annot_pencil(event, res=(width,height))
        elif event["type"] == "line":
            svg += annot_line(event, res=(width,height))
        elif event["type"] == "ellipse":
            svg += annot_ellipse(event, res=(width,height))
        elif event["type"] == "rectangle":
            svg += annot_rectangle(event, res=(width,height))
        elif event["type"] == "triangle":
            svg += annot_triangle(event, res=(width,height))
        elif event["type"] == "text":
            svg += annot_text(event, res=(width,height))
        else:
            print("Unknown annotation type: %s" % event["type"])

    svg += '</svg>'
    return svg

curpresentation = None
curslide = None
sessionstart = 0
sessionend = 0
frame = 0
melt = "melt"

frames = []
audiotracks = []
deskshares = {}
webcams = {}
users = {}

for event in recording['event']:
    drawframe = False

    if event["@eventname"] in IGNORE_EVENTS:
        continue

    # session starteda
    if event["@eventname"] == "CreatePresentationPodEvent":
        sessionstart = int(event['timestampUTC']) / 1000
    timestamp = int(event["timestampUTC"])/1000 - sessionstart

    # user joined
    if event["@eventname"] == "ParticipantJoinEvent":
        users[event['userId']] = event['name']
        continue

    # start audio recording
    if event["@eventname"] == "StartRecordingEvent":
        if audiotracks:
            audiotracks[-1]['length'] = timestamp - audiotracks[-1]['time']
        audiotracks.append({'opus': "audio/%s" % event['filename'].split('/')[-1], 'time': timestamp})
        continue

    # start desktop recording
    if event["@eventname"] == "StartWebRTCDesktopShareEvent":
        print("Starting Desktop share")
        filename = event['filename'].split('/')[-1]
        deskshares[filename] = {'time': timestamp, 'webm': 'deskshare/%s' % filename}
        continue

    # stop desktop recording
    if event["@eventname"] == "StopWebRTCDesktopShareEvent":
        print("Stopping Desktop share")
        filename = event['filename'].split('/')[-1]
        deskshares[filename]['length'] = timestamp - deskshares[filename]['time']
        continue

    # start webcam recording
    if event["@eventname"] == "StartWebRTCShareEvent":
        filename = event['filename'].split('/')[-1]
        dirname = event['filename'].split('/')[-2]
        userid = filename.split('-')[1]
        print("Starting Webcam share for %s" % users[userid])
        webcams[filename] = {'time': timestamp, 'nick': users[userid], 'webm': 'video/%s/%s' % (dirname, filename)}
        continue

    # stop desktop recording
    if event["@eventname"] == "StopWebRTCShareEvent":
        filename = event['filename'].split('/')[-1]
        print("Stopping Webcam share for %s" % webcams[filename]['nick'])
        webcams[filename]['length'] = timestamp - webcams[filename]['time']
        continue

    # presentation switched (could be new or old)
    if event["@eventname"] == "SharePresentationEvent":
        print("Changing presentation to %s" % event["presentationName"])
        drawframe = True
        curpresentation = event["presentationName"]
        curslide = 0

        if curpresentation not in presentations:
            presentations[curpresentation] = {}
            presentations[curpresentation]['slides'] = []
            for svgslide in sorted(glob.glob("presentation/%s/svgs/slide*.svg" % curpresentation), key=lambda x: int(x.split('/')[-1].lstrip('slide').rstrip('.svg'))):
                slide = {}
                print("Loading svg %s" % svgslide)
                slide['origsvg'] = open(svgslide, 'r').read()
                slide['drawings'] = {}
                presentations[curpresentation]['slides'].append(slide)

    # change slide
    elif event["@eventname"] == "GotoSlideEvent":
        print("Changing to slide %s" % event['slide'])
        drawframe = True
        curpresentation = event["presentationName"]
        curslide = int(event['slide'])

    # add shape to slide
    elif event["@eventname"] == "AddShapeEvent":
        print("Adding shape")
        drawframe = True
        presentation, slidestr = event["whiteboardId"].split('/')
        slide = int(slidestr) - 1
        if event["status"] == "DRAW_END":
            presentations[presentation]['slides'][slide]['drawings'][event["shapeId"]] = event
        else:
            continue

    # delete shape from slide
    elif event["@eventname"] == "UndoAnnotationEvent":
        print("Removing shape")
        drawframe = True
        presentation, slidestr = event["whiteboardId"].split('/')
        slide = int(slidestr) - 1
        del presentations[presentation]['slides'][slide]['drawings'][event['shapeId']]

    elif event["@eventname"] == "EndAndKickAllEvent":
        sessionend = timestamp

    # unknown event
    else:
        pass
        #print("Unknown event: %s" % event["@eventname"])
        #print(json.dumps(event))

    # render slide
    if drawframe:
        svg = render(presentations[curpresentation]['slides'][curslide])
        open("frames/%d.svg" % frame, "w").write(svg)
        subprocess.call(["rsvg-convert", "-f", "png", "frames/%d.svg" % frame, "-h", "1080", "-o", "frames/%d.png" % frame])
        if frames:
            frames[-1]['length'] = timestamp - frames[-1]['time']
        frames.append({'png': 'frames/%d.png' % frame, 'time': timestamp})
        frame += 1

if frames:
    frames[-1]['length'] = sessionend - frames[-1]['time']

if audiotracks:
    audiotracks[-1]['length'] = sessionend - audiotracks[-1]['time']

webcams = list(webcams.values())
deskshares = list(deskshares.values())

for webcam in webcams:
    if 'length' not in webcam:
        webcam['length'] = sessionend - webcam['time']

for deskshare in deskshares:
    if 'length' not in deskshare:
        deskshare['length'] = sessionend - deskshare['time']

kdenlive = """<?xml version='1.0' encoding='utf-8'?>
<mlt LC_NUMERIC="C" producer="main_bin" version="6.22.1" root="{os.getcwd()}">
<profile frame_rate_num="25" sample_aspect_num="1" display_aspect_den="9" colorspace="709" progressive="1" description="HD 1080p 25 fps" display_aspect_num="16" frame_rate_den="1" width="1920" height="1080" sample_aspect_den="1"/>
"""

def formattime(timestamp):
    hours, remainder = divmod(timestamp, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%06.3f" % (hours, minutes, seconds)

for i, frame in enumerate(frames):
    kdenlive += f"""
        <producer id="frame{i}" in="00:00:00.000" out="{formattime(frame['length'])}">
            <property name="length">{formattime(frame['length'])}</property>
            <property name="eof">pause</property>
            <property name="resource">{frame['png']}</property>
            <property name="ttl">25</property>
            <property name="aspect_ratio">1</property>
            <property name="progressive">1</property>
            <property name="seekable">1</property>
            <property name="meta.media.width">1920</property>
            <property name="meta.media.height">1080</property>
            <property name="mlt_service">qimage</property>
            <property name="global_feed">1</property>
        </producer>
        """

for i, webcam in enumerate(webcams):
    kdenlive += f"""
        <producer id="webcam{i}" in="00:00:00.000" out="{formattime(webcam['length'])}">
            <property name="length">{formattime(webcam['length'])}</property>
            <property name="eof">pause</property>
            <property name="resource">{webcam['webm']}</property>
            <property name="ttl">25</property>
            <property name="aspect_ratio">1</property>
            <property name="progressive">1</property>
            <property name="seekable">1</property>
            <property name="meta.media.width">1920</property>
            <property name="meta.media.height">1080</property>
            <property name="mlt_service">avformat</property>
            <property name="global_feed">1</property>
        </producer>
        """

for i, deskshare in enumerate(deskshares):
    kdenlive += f"""
        <producer id="deskshare{i}" in="00:00:00.000" out="{formattime(deskshare['length'])}">
            <property name="length">{formattime(deskshare['length'])}</property>
            <property name="eof">pause</property>
            <property name="resource">{deskshare['webm']}</property>
            <property name="ttl">25</property>
            <property name="aspect_ratio">1</property>
            <property name="progressive">1</property>
            <property name="seekable">1</property>
            <property name="meta.media.width">1920</property>
            <property name="meta.media.height">1080</property>
            <property name="mlt_service">avformat</property>
            <property name="global_feed">1</property>
        </producer>
        """

for i, audiotrack in enumerate(audiotracks):
    kdenlive += f"""
        <producer id="audiotrack{i}" in="00:00:00.000" out="{formattime(audiotrack['length'])}">
            <property name="resource">{audiotrack['opus']}</property>
  <property name="meta.media.nb_streams">1</property>
  <property name="meta.media.0.stream.type">audio</property>
  <property name="meta.media.0.codec.sample_fmt">fltp</property>
  <property name="meta.media.0.codec.sample_rate">48000</property>
  <property name="meta.media.0.codec.channels">1</property>
  <property name="meta.media.0.codec.name">opus</property>
  <property name="meta.media.0.codec.long_name">Opus</property>
  <property name="meta.media.0.codec.bit_rate">0</property>
  <property name="meta.attr.0.stream.METADATA.markup">Freeswitch/mod_opusfile</property>
            <property name="eof">pause</property>
            <property name="seekable">1</property>
            <property name="mute_on_pause">1</property>
            <property name="mlt_service">avformat</property>
            <property name="global_feed">1</property>
        </producer>
    """

kdenlive += """
 <playlist id="main_bin">
  <property name="kdenlive:docproperties.activeTrack">0</property>
  <property name="kdenlive:docproperties.audioChannels">2</property>
  <property name="kdenlive:docproperties.audioTarget">0</property>
  <property name="kdenlive:docproperties.disablepreview">0</property>
  <property name="kdenlive:docproperties.enableTimelineZone">0</property>
  <property name="kdenlive:docproperties.enableexternalproxy">0</property>
  <property name="kdenlive:docproperties.enableproxy">0</property>
  <property name="kdenlive:docproperties.externalproxyparams"/>
  <property name="kdenlive:docproperties.generateimageproxy">0</property>
  <property name="kdenlive:docproperties.generateproxy">0</property>
  <property name="kdenlive:docproperties.kdenliveversion">20.08.0</property>
  <property name="kdenlive:docproperties.position">0</property>
  <property name="kdenlive:docproperties.previewextension"/>
  <property name="kdenlive:docproperties.previewparameters"/>
  <property name="kdenlive:docproperties.profile">atsc_1080p_25</property>
  <property name="kdenlive:docproperties.proxyextension">mkv</property>
  <property name="kdenlive:docproperties.proxyimageminsize">2000</property>
  <property name="kdenlive:docproperties.proxyimagesize">800</property>
  <property name="kdenlive:docproperties.proxyminsize">1000</property>
  <property name="kdenlive:docproperties.proxyparams">-vf yadif,scale=960:-2 -qscale 3 -vcodec mjpeg -acodec pcm_s16le</property>
  <property name="kdenlive:docproperties.scrollPos">0</property>
  <property name="kdenlive:docproperties.seekOffset">30000</property>
  <property name="kdenlive:docproperties.version">1</property>
  <property name="kdenlive:docproperties.verticalzoom">1</property>
  <property name="kdenlive:docproperties.videoTarget">0</property>
  <property name="kdenlive:docproperties.zonein">0</property>
  <property name="kdenlive:docproperties.zoneout">75</property>
  <property name="kdenlive:docproperties.zoom">8</property>
  <property name="kdenlive:expandedFolders"/>
  <property name="kdenlive:documentnotes"/>
  <property name="xml_retain">1</property>
"""

# main bin
for i, frame in enumerate(frames):
    kdenlive += f"""
        <entry producer="frame{i}" in="00:00:00.000" out="{formattime(frame['length'])}"/>
    """

for i, audiotrack in enumerate(audiotracks):
    kdenlive += f"""
        <entry producer="audiotrack{i}" in="00:00:00.000" out="{formattime(audiotrack['length'])}"/>
    """

for i, webcam in enumerate(webcams):
    kdenlive += f"""
        <entry producer="webcam{i}" in="00:00:00.000" out="{formattime(webcam['length'])}"/>
    """

for i, deskshare in enumerate(deskshares):
    kdenlive += f"""
        <entry producer="deskshare{i}" in="00:00:00.000" out="{formattime(deskshare['length'])}"/>
    """


kdenlive += "</playlist>"

# slides
kdenlive += """<playlist id="playlist0">"""
if frames:
    kdenlive += f"""<blank length="{formattime(frames[0]['time'])}"/>"""
    for i, frame in enumerate(frames):
        kdenlive += f"""
            <entry producer="frame{i}" in="00:00:00.000" out="{formattime(frame['length'])}"/>
        """
else:
    kdenlive += f"""<blank length="{formattime(sessionend-sessionstart)}"/>"""
kdenlive += """</playlist>"""

# audio
kdenlive += """<playlist id="playlist1"><property name="kdenlive:audio_track">1</property>"""
if audiotracks:
    kdenlive += f"""<blank length="{formattime(audiotracks[0]['time'])}"/>"""
    for i, audiotrack in enumerate(audiotracks):
        kdenlive += f"""
            <entry producer="audiotrack{i}" in="00:00:00.000" out="{formattime(audiotrack['length'])}"/>
        """
else:
    kdenlive += f"""<blank length="{formattime(sessionend-sessionstart)}"/>"""
kdenlive += """</playlist>"""

for i, deskshare in enumerate(deskshares):
    kdenlive += f"""
        <playlist id="deskshareplaylist{i}">
            <blank length="{formattime(deskshare['time'])}"/>
            <entry producer="deskshare{i}" in="00:00:00.000" out="{formattime(deskshare['length'])}"/>
        </playlist>
    """

for i, webcam in enumerate(webcams):
    kdenlive += f"""
        <playlist id="webcamplaylist{i}">
            <blank length="{formattime(webcam['time'])}"/>
            <entry producer="webcam{i}" in="00:00:00.000" out="{formattime(webcam['length'])}"/>
        </playlist>
    """

kdenlive += """<playlist id="playlist2"/>"""

for i, deskshare in enumerate(deskshares):
    kdenlive += f"""
        <tractor id="desksharetractor{i}" in="00:00:00.000" out="{formattime(sessionend)}">
            <property name="kdenlive:audio_track">0</property>
            <property name="kdenlive:trackheight">69</property>
            <property name="kdenlive:collapsed">0</property>
            <property name="kdenlive:thumbs_format"/>
            <property name="kdenlive:audio_rec"/>
            <property name="kdenlive:timeline_active">1</property>
            <track producer="deskshareplaylist{i}"/>
            <track hide="both" producer="playlist2"/>
        </tractor>
    """

for i, webcam in enumerate(webcams):
    kdenlive += f"""
        <tractor id="webcamtractor{i}" in="00:00:00.000" out="{formattime(sessionend)}">
            <property name="kdenlive:audio_track">0</property>
            <property name="kdenlive:trackheight">69</property>
            <property name="kdenlive:collapsed">0</property>
            <property name="kdenlive:thumbs_format"/>
            <property name="kdenlive:audio_rec"/>
            <property name="kdenlive:timeline_active">1</property>
            <track producer="webcamplaylist{i}"/>
            <track hide="both" producer="playlist2"/>
        </tractor>
    """

kdenlive += f"""
 <tractor id="tractor0" in="00:00:00.000" out="{formattime(sessionend)}">
  <property name="kdenlive:audio_track">0</property>
  <property name="kdenlive:trackheight">69</property>
  <property name="kdenlive:collapsed">0</property>
  <property name="kdenlive:thumbs_format"/>
  <property name="kdenlive:audio_rec"/>
  <property name="kdenlive:timeline_active">1</property>
  <track producer="playlist0"/>
  <track hide="both" producer="playlist2"/>
 </tractor>
 <tractor id="tractor1" in="00:00:00.000" out="{formattime(sessionend)}">
  <property name="kdenlive:audio_track">1</property>
  <property name="kdenlive:trackheight">69</property>
  <property name="kdenlive:collapsed">0</property>
  <property name="kdenlive:thumbs_format"/>
  <property name="kdenlive:audio_rec"/>
  <property name="kdenlive:timeline_active">1</property>
  <track producer="playlist1"/>
  <track hide="both" producer="playlist2"/>
 </tractor>
 <tractor id="tractor2" global_feed="1" in="00:00:00.000" out="{formattime(sessionend)}">
  <track producer="tractor1"/>
  <track producer="tractor0"/>
"""

for i, deskshare in enumerate(deskshares):
    kdenlive += f"""<track producer="desksharetractor{i}"/>"""

for i, webcam in enumerate(webcams):
    kdenlive += f"""<track producer="webcamtractor{i}"/>"""

kdenlive += f"""
  <transition id="transition0">
   <property name="a_track">0</property>
   <property name="b_track">1</property>
   <property name="compositing">0</property>
   <property name="distort">0</property>
   <property name="rotate_center">0</property>
   <property name="mlt_service">qtblend</property>
   <property name="kdenlive_id">qtblend</property>
   <property name="internal_added">237</property>
   <property name="always_active">1</property>
  </transition>
  <filter id="filter0">
   <property name="window">75</property>
   <property name="max_gain">20dB</property>
   <property name="mlt_service">volume</property>
   <property name="internal_added">237</property>
   <property name="disable">1</property>
  </filter>
  <filter id="filter1">
   <property name="channel">-1</property>
   <property name="mlt_service">panner</property>
   <property name="internal_added">237</property>
   <property name="start">0.5</property>
   <property name="disable">1</property>
  </filter>
  <filter id="filter2">
   <property name="iec_scale">0</property>
   <property name="mlt_service">audiolevel</property>
   <property name="disable">1</property>
  </filter>
 </tractor>
"""

kdenlive += "</mlt>"


open("%s.kdenlive" % os.path.basename(path), "w").write(kdenlive)
