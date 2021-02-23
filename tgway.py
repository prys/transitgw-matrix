#!/usr/bin/env python3
import boto3
import json
import datetime
from botocore.config import Config

config = Config(
    retries = dict(
        max_attempts = 10
    )
)
now = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")

# Get route table associated with an attachment
def getRtbl(attachName):
  if 'Association' in attachName:
    rtbName = attachName['Association']['TransitGatewayRouteTableId']
    return(rtbName)
  else:
    return("NULL")

# Check whether a return route exists for a particular route
def chkReturn(attachSrc, routeTbl):
  if routeTbl != "NULL":
    retRoutes = ec2cli.search_transit_gateway_routes(TransitGatewayRouteTableId=routeTbl,Filters=[{'Name':'state', 'Values':['active','blackhole']}])
    for z in range(len(retRoutes['Routes'])):
      if 'TransitGatewayAttachments' in retRoutes['Routes'][z]: # check the route references an attachment
        retRouteCheck = retRoutes['Routes'][z]['TransitGatewayAttachments'][0]['TransitGatewayAttachmentId']
        if retRouteCheck == attachSrc:
          return(True)
  return(False)

def getAttachList(attachments, aliasJson):
  attachList = []
  for a in range(len(attachments)):
    id = attachments[a]['TransitGatewayAttachmentId']
    for tag in attachments[a]['Tags']: # loop round tags and find the Name
      if tag['Key'] == "Name":
        attachName = tag['Value']
    if attachName in aliasJson: # check if we have a friendly name in the alias json
      friendlyName = aliasJson[attachName]
    else:
      friendlyName = attachName
    type = attachments[a]['ResourceType']
    association = attachments[a]['Association']
    attachList.append({'FriendlyName': friendlyName, 'Name': attachName, 'TransitGatewayAttachmentId': id, 'ResourceType': type, 'Association': association})
  return(attachList)

# Load alias file. This is a json file that maps Transit Gateway attachments to more recognisable VPC names.
try:
  with open('alias.json') as aliasFile:
    aliasJson = json.load(aliasFile)
except FileNotFoundError:
  print("This script looks for a file called alias.json to map Transit Gateway attachment IDs to more 'friendly' names of VPCs")
  aliasJson = ""

ec2cli = boto3.client('ec2', config=config)
tgAttach = ec2cli.describe_transit_gateway_attachments()
tgAttach = getAttachList(tgAttach['TransitGatewayAttachments'], aliasJson)
tgAttach = sorted(tgAttach, key = lambda i: (i['ResourceType'], i['FriendlyName'])) # Sort by resource type & friendly name (in that precedence)

matrixSize = len(tgAttach)
routeMatrix = [["<td></td>" for i in range(matrixSize+3)] for j in range(matrixSize+1)]
routeMatrix[0][0] = """<th>Attachment Id</th>"""
routeMatrix[0][1] = """<th>Attachment (Friendly)</th>"""

for i in range(len(tgAttach)): # loop round each attachment
  print('Processing attachment: ' + str(i+1) + ' of ' + str(len(tgAttach)) + '\r', end="", flush=True)
  attachId =  tgAttach[i]['TransitGatewayAttachmentId']
  attachFriendlyName = tgAttach[i]['FriendlyName']
  attachName = tgAttach[i]['Name']
  attachType = tgAttach[i]['ResourceType']
  routeMatrix[i+1][0] = """<td id=""" + attachType + ">""" + attachId + "</td>"
  attachId =  tgAttach[i]['TransitGatewayAttachmentId']
  routeTable = getRtbl(tgAttach[i])
  routeMatrix[i+1][i+2] = """<td id="self"></td>""" # own route
  if routeTable != "NULL":
    routeMatrix[i+1][matrixSize+2] = """<td id=""" + attachType + ">""" + routeTable + """</td>"""
    tgroutes = ec2cli.search_transit_gateway_routes(TransitGatewayRouteTableId=routeTable,Filters=[{'Name':'state', 'Values':['active','blackhole']}])
    # loop round each attachment again, to match against the attachment associated with the specific route.  An attachment can have multiple, seperate routes (CIDRs) pointing to another single TGW attachment as a destination).  I.E:
    # tgw-attach-a-rtbl:
    #     10.1.0.0/16 --> tgw-attach-b
    #     10.2.0.0/16 --> tgw-attach-b
    #     10.3.0.0/16 --> tgw-attach-b
    for y in range(len(tgAttach)):
      cidrArray = []
      routeStateArray = []
      for x in range(len(tgroutes['Routes'])): # loop round each route within the route table
        routeState = tgroutes['Routes'][x]['State']
        if 'TransitGatewayAttachments' in tgroutes['Routes'][x]: # check the route references an attachment
          routeAttach = tgroutes['Routes'][x]['TransitGatewayAttachments'][0]['TransitGatewayAttachmentId'] # need to watch this - not sure why it's an array as each route can only be directed at a single attachment
          routeCIDR = tgroutes['Routes'][x]['DestinationCidrBlock']
          testAttach = tgAttach[y]['TransitGatewayAttachmentId']
          if testAttach == routeAttach: # if there's a match, test to see if the return route is in place...
            returnRtbl = getRtbl(tgAttach[y])
            retRouteFound = chkReturn(attachId, returnRtbl)
            if retRouteFound:
              if routeState == "active":
                routeStateArray.append('active')
                cidrArray.append(routeCIDR + ' : &#9989;')
              else:
                routeStateArray.append('blackhole')
                cidrArray.append(routeCIDR + ' : &#128310;')
            else:
              routeStateArray.append('oneway')
              cidrArray.append(routeCIDR + ' : &#10060;')
        else:
          routeStateArray.append('blackhole')
          cidrArray.append(routeCIDR + ' : &#128310;')
      separator = '<br />'
      # each if condition supersedes the previous condition.  The 'td id' is specified by whether any routes are found.
      #   If route is active and has return route : td id = route (green background)
      #   If any blackholes are found             : td id = blackhole (Yellow)
      #   If no return routes are found           : td id = oneway (Red)
      if 'active' in routeStateArray:
        routeMatrix[i+1][y+2] = """<td id="route"><div data-html="true" class="tooltip">X<span class="tooltiptext">""" + separator.join(cidrArray) + """</span></div></td>"""       # Correct route found
      if 'blackhole' in routeStateArray:
        routeMatrix[i+1][y+2] =  """<td id="blackhole"><div data-html="true" class="tooltip">X<span class="tooltiptext">""" + separator.join(cidrArray) + """</span></div></td>"""  # Return route found, but route is a blackhole
      if 'oneway' in routeStateArray:
        routeMatrix[i+1][y+2] = """<td id="oneway"><div data-html="true" class="tooltip">X<span class="tooltiptext">""" + separator.join(cidrArray) + """</span></div></td>"""      # Missing return route
  else:
    routeMatrix[i+1][matrixSize+2] = """<td id="noRoute">No route table attached</td>"""
  routeMatrix[i+1][1] = """<td id=""" + attachType + ">""" + attachFriendlyName + """</td>"""
  routeMatrix[0][i+2] = """<th id=""" + attachType + "><span>""" + attachFriendlyName + """</span></th>"""

#Write out html file from the matrix variable
routeMatrix[0][matrixSize+2] = """<th>Route Table</th>"""
f = open("transit.html", "w")
htmlhead = """<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="style.css">
<link href="https://fonts.googleapis.com/css?family=Quicksand:300,500" rel="stylesheet">
<title>Transit Gateway Routing Matrix</title>
</head>
<body>
<h1>Transit Gateway Routing Matrix</h1>
<p class="it">(Generated: """ + now + """)</p>
<br>
<table>"""

f.write(htmlhead)

for row in routeMatrix:
  f.write("<tr>")
  for val in row:
    f.write(val)
  f.write("</tr>")

htmlfoot = """
</table>
<br><br>
<table style="width:20%">
<tr><th colspan="2">Key</th></tr>
<tr><td id="route" style="padding-left:5px;padding-right:5px">X</td><td style="text-align:left;padding-left:10px">Route Found with matching return route</td></tr>
<tr><td id="blackHole">X</td><td style="text-align:left;padding-left:10px">Blackhole</td></tr>
<tr><td id="oneway">X</td><td style="text-align:left;padding-left:10px">Route Found but no return route</td></tr>
<tr><td id="self"></td><td style="text-align:left;padding-left:10px">N/A - Own Route</td></tr>
</table>
</body>
</html>"""
f.write(htmlfoot)
f.close()
