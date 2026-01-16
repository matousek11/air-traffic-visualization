import redis
from datetime import datetime
# Packages for XML pretty print
import xml.dom.minidom

# Use initialization with default port 6379
r = redis.Redis(host='10.15.2.203')

# Get Publish/Subscribe object
p = r.pubsub()

p.subscribe('css:b2b:rep:karelhtut3:1')
# First message is Redis confirmation - subscribing result (after waiting some time) 
print(p.get_message(timeout=0.1))

# Update the requested time range
xml_request = """<?xml version="1.0"?>
<flight:FlightListByAirspaceRequest xmlns:flight="eurocontrol/cfmu/b2b/FlightServices">
  <endUserId>karelhtut3</endUserId>
  <sendTime>{}</sendTime>
  <dataset>
    <type>OPERATIONAL</type>
  </dataset>
  <includeProposalFlights>false</includeProposalFlights>
  <includeForecastFlights>false</includeForecastFlights>
  <trafficType>DEMAND</trafficType>
  <trafficWindow>
    <wef>2025-06-15 19:00</wef>
    <unt>2025-06-15 19:20</unt>
  </trafficWindow>
  <requestedFlightFields>flightState</requestedFlightFields>
  <requestedFlightFields>ccamsSSRCode</requestedFlightFields>
  <requestedFlightFields>aircraftType</requestedFlightFields>
  <requestedFlightFields>estimatedTimeOfArrival</requestedFlightFields>
  <countsInterval>
    <duration>0001</duration>
    <step>0001</step>
  </countsInterval>
  <calculationType>ENTRY</calculationType>
  <airspace>LK</airspace>
</flight:FlightListByAirspaceRequest>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

xml_request2 = """<?xml version="1.0"?>
<flight:FlightRetrievalRequest xmlns:flight="eurocontrol/cfmu/b2b/FlightServices">
  <endUserId>karelhtut3</endUserId>
  <sendTime>{}</sendTime>
  <dataset>
    <type>OPERATIONAL</type>
  </dataset>
  <includeProposalFlights>false</includeProposalFlights>
  <flightId>
      <keys>
          <aircraftId>DLA4MJ</aircraftId>
          <aerodromeOfDeparture>EPWR</aerodromeOfDeparture>
          <nonICAOAerodromeOfDeparture>false</nonICAOAerodromeOfDeparture>
          <airFiled>false</airFiled>
          <aerodromeOfDestination>EDDF</aerodromeOfDestination>
          <nonICAOAerodromeOfDestination>false</nonICAOAerodromeOfDestination>
          <estimatedOffBlockTime>2025-06-15 18:40</estimatedOffBlockTime>
      </keys>
  </flightId>
  <requestedFlightDatasets>flight</requestedFlightDatasets>
  <requestedFlightFields>lastKnownPosition</requestedFlightFields>
</flight:FlightRetrievalRequest>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Publish each JSON request to channel
print(r.publish('css:b2b:req:karelhtut3:1', xml_request2.encode(encoding="utf-8")))

# Obtain data message from Response channel (with significant delay)
message = p.get_message(timeout=10.0) 
if message is None: 
    print('No result obtained.')
else:
    print('Result obtained.')

if message is not None:
    # Prity print of obtained response data - without main flights content
    print("XML Result:")
    raw_data = message['data']
    print("Raw message data:", repr(raw_data))
    # Parse XML to xmk.dom structure
    result = xml.dom.minidom.parseString(message['data'].decode("utf-8"))
    # Remove the flight list from xml.dom
    #textnode = result.createTextNode("...Flights list removed...")
    nodes = result.getElementsByTagName("flights")
    for node in nodes:
        parent = node.parentNode
        parent.removeChild(node)
        #parent.appendChild(textnode)
    # Pretty print the xml result
    print(result.toprettyxml())

    # Save obtained response data directly to File
    newFile = open("LKFlightsResults.xml", "wb")
    newFile.write(message['data'])
    newFile.close()
    print("Result file created...")