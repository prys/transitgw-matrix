# transitgw-matrix
This script builds a html table showing a Transit Gateway routing matrix - i.e. which attachments route to which others. For each route, the script checks there's a valid return route and flags it as red if not. If the route is a blackhole (e.g. incomplete VPN configuration), the route is flagged as yellow.

The script uses the attached alias.json file, which provides a mapping between the Transit Gateway attachment IDs and a more friendly, recognisable name. If there isn't a mapping in the file, it will just use the attachment ID.

There is a dependency on the **boto3** library ('pip3 install boto3' if required)

The script will output a file called transit.html in the folder where the script was run. Formatting of the table is via the attached style.css file.
