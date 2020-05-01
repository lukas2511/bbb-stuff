#!/usr/bin/env python3

import xmltodict
import json
import re
import glob
import os
import subprocess

# throw into raw recording directory next to events.xml and run, should generate out/*.pdf

recording = xmltodict.parse(open("events.xml").read())['recording']

IGNORE_EVENTS = [
    'WhiteboardCursorMoveEvent',
    'AssignPresenterEvent',
    'ConversionCompletedEvent',
    'CreatePresentationPodEvent',
    'EndAndKickAllEvent',
    'ParticipantJoinedEvent',
    'ParticipantJoinEvent',
    'SetPresentationDownloadable',
    'SetPresenterInPodEvent',
    'StartRecordingEvent',
    'SharePresentationEvent',
    'ResizeAndMoveSlideEvent',
    'GotoSlideEvent',
]

drawings = {}

for event in recording['event']:
    if event["@eventname"] in IGNORE_EVENTS:
        continue
    elif event["@eventname"] == "UndoAnnotationEvent":
        if event["shapeId"] in drawings[event["whiteboardId"]]:
            del drawings[event["whiteboardId"]][event["shapeId"]]
    elif event["@eventname"] == "AddShapeEvent":
        whiteboard = event["whiteboardId"]
        if whiteboard not in drawings:
            drawings[whiteboard] = {}
        if event["status"] == "DRAW_END":
            drawings[whiteboard][event["shapeId"]] = event

    else:
        print("Unknown event: %s" % event["@eventname"])

def get_datapoints(event):
    return list([(float(x)/100, float(y)/100) for x, y in re.findall(r'([^,]+),([^,]+)', event['dataPoints'])])

def annot_pencil(event):
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

def annot_line(event):
    event["commands"] = "1,2"
    return annot_pencil(event)

def annot_ellipse(event):
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

def annot_rectangle(event):
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

def annot_triangle(event):
    datapoints = get_datapoints(event)
    print(datapoints)
    xBottomLeft, yTop = datapoints[0]
    xBottomRight, yBottomLeft = datapoints[1]
    yBottomRight = yBottomLeft
    xTop = (xBottomRight - xBottomLeft)/2 + xBottomLeft

    d = "M%s, %s, %s, %s, %s, %s Z" % (xTop*width, yTop*height, xBottomLeft*width, yBottomLeft*height, xBottomRight*width, yBottomRight*height)

    svg = '<path d="%s" fill="none" stroke="#%06x" stroke-width="%s" />' % (d, int(event['color']), float(event['thickness'])/100*width)
    return svg

def annot_text(event):
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

    print(json.dumps(event, indent=4))
    return svg

def process(origsvg, drawing):
    global width, height
    width, height = 1920, 1080
    origsvg = origsvg.replace("</svg>", "")
    for shapeid, event in drawing.items():
        if event["type"] == "pencil":
            origsvg += annot_pencil(event)
        elif event["type"] == "line":
            origsvg += annot_line(event)
        elif event["type"] == "ellipse":
            origsvg += annot_ellipse(event)
        elif event["type"] == "rectangle":
            origsvg += annot_rectangle(event)
        elif event["type"] == "triangle":
            origsvg += annot_triangle(event)
        elif event["type"] == "text":
            origsvg += annot_text(event)
        else:
            print("unknown annotation type: %s" % event["type"])
    origsvg += "</svg>"
    return origsvg

for presdir in glob.glob("presentation/*"):
    presid = os.path.basename(presdir)
    if not os.path.exists("out"):
        os.mkdir("out")
    if not os.path.exists("out/" + presid):
        os.mkdir("out/" + presid)

    num_pages = len(glob.glob(presdir + "/svgs/slide*.svg"))

    for page in range(1, num_pages+1):
        origsvg = open(presdir + "/svgs/slide%d.svg" % page).read()
        if '%s/%d' % (presid, page) in drawings:
            origsvg = process(origsvg, drawings['%s/%d' % (presid, page)])
        open("out/" + presid + "/slide%d.svg" % page, "w").write(origsvg)
        subprocess.call(["rsvg-convert", "-f", "pdf", "out/" + presid + "/slide%d.svg" % page, "-o", "out/" + presid + "/slide%d.pdf" % page])
    if os.path.exists("out/%s.pdf" % presid):
        os.unlink("out/%s.pdf" % presid)
    subprocess.call(["pdfjoin", "-o", "out/%s.pdf" % presid] + list(["out/" + presid + "/slide%d.pdf" % page for page in range(1, num_pages+1)]))
