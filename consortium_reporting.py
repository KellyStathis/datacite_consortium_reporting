import requests
import base64
import dateparser
from datetime import date
import csv
import os
from dotenv import load_dotenv

def get_datacite_api_response(authorization, base_url, url_extension, querystring=""):
    # Headers for all API requests
    headers = {
        "accept": "application/vnd.api+json",
        "authorization": authorization
    }
    url = base_url + url_extension
    response = requests.request("GET", url, headers=headers, params=querystring)
    return response.json()

def main():
    load_dotenv()
    consortium_id = os.getenv('CONSORTIUM_ID')
    consortium_pass = os.getenv('CONSORTIUM_PASS')
    test_instance = os.getenv('TEST_INSTANCE')
    userpass = consortium_id + ":" + consortium_pass
    authorization = "Basic {}".format(base64.b64encode(userpass.encode()).decode())
    query_year = os.getenv('YEAR')
    former_members = os.getenv('FORMER_MEMBERS').split(";")

    # Set base url (prod or test)
    if test_instance and test_instance.lower() == "true":
        instance_type = "Test"
        base_url = "https://api.test.datacite.org/"
    else:
        instance_type = "Production"
        base_url = "https://api.datacite.org/"

    month_keys = []
    for month in range (1, 13):
        month_keys.append(query_year + "-" + "{:02d}".format(month))

    # Get data for consortium
    consortium_data = get_datacite_api_response(authorization, base_url, "/providers/" + consortium_id.lower())

    # Grab the list of consortium organizations
    org_list = consortium_data["data"]["relationships"]["consortiumOrganizations"]["data"]
    dois_by_org = {}

    # Get all DOIs from the consortium for the year
    for org in org_list:
        if org["id"] in former_members: # Exclude former members
            continue
        print("Getting DOIs for: " + org["id"])

        # Get org data
        consortium_org_data = get_datacite_api_response(authorization, base_url, "/providers/" + org["id"])
        org["data"] = consortium_org_data["data"]

        # Set up dict for consortium org
        dois_by_org[org["id"]] = {"name": org["data"]["attributes"]["name"], "dois": [], "monthly_totals": {}}
        for month in month_keys:
            dois_by_org[org["id"]]["monthly_totals"][month] = 0

        # Get total count of DOIs across all years
        consortium_org_all_dois = get_datacite_api_response(authorization, base_url, "/dois", {"provider-id": org["id"]})
        dois_by_org[org["id"]]["cumulative_total"] = consortium_org_all_dois["meta"]["total"]

        # Save initial list of DOIs from query year
        page_number = 1
        page_size = 1000
        consortium_org_year_dois = get_datacite_api_response(authorization, base_url, "/dois", {"provider-id": org["id"], "created": query_year, "page[number]": str(page_number), "page[size]": str(page_size)})
        totalPages = consortium_org_year_dois["meta"]["totalPages"]
        dois_by_org[org["id"]]["annual_total"] = consortium_org_year_dois["meta"]["total"]

        # Add DOIs to consortium org list
        dois_by_org[org["id"]]["dois"].extend(consortium_org_year_dois["data"])
        page_number += 1

        # Extend list of DOIs with subsequent pages
        while page_number <= totalPages:
            consortium_org_year_dois = get_datacite_api_response(authorization, base_url, "/dois", {"provider-id": org["id"], "created": query_year, "page[number]": str(page_number), "page[size]": str(page_size)})
            dois_by_org[org["id"]]["dois"].extend(consortium_org_year_dois["data"])
            page_number += 1

    # Count DOIs from the consortium
    consortium_totals = {}
    for month in month_keys:
        consortium_totals[month] = 0
    consortium_totals["annual_total"] = 0
    consortium_totals["cumulative_total"] = 0
    for org in dois_by_org:
        print("Counting DOIs for: " + org)
        # Count how many DOIs the organization minted each month
        for doi in dois_by_org[org]["dois"]:
            doi_date = dateparser.parse(doi["attributes"]["created"])
            dois_by_org[org]["monthly_totals"][str(doi_date.year) + "-" + "{:02d}".format(doi_date.month)] += 1
        # Add the organization's monthly totals to the consortium's
        for month in dois_by_org[org]["monthly_totals"]:
            consortium_totals[month] += dois_by_org[org]["monthly_totals"][month]
        # Add the organization's annual total to the consortium's
        consortium_totals["annual_total"] += dois_by_org[org]["annual_total"]
        # Add the organization's cumulative total to the consortium's
        consortium_totals["cumulative_total"] += dois_by_org[org]["cumulative_total"]

    # Write DOI counts to csv file
    output_filename = str(date.today()) + "_" + consortium_id + "_" + instance_type + "_dois.csv"
    with open(output_filename, mode='w') as csv_file:
        fieldnames = ["org_id", "org_name"] + month_keys + ["annual_total", "cumulative_total"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for org in dois_by_org:
            org_row = {"org_id": org, "org_name": dois_by_org[org]["name"]}
            org_row.update(dois_by_org[org]["monthly_totals"])
            org_row["annual_total"] = dois_by_org[org]["annual_total"]
            org_row["cumulative_total"] = dois_by_org[org]["cumulative_total"]
            writer.writerow(org_row)
        consortium_row = {"org_id": consortium_id.lower(), "org_name": "[All members]"}
        consortium_row.update(consortium_totals)
        writer.writerow(consortium_row)

if __name__ == "__main__":
    main()