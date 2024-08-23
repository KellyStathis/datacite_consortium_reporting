import requests
from datetime import date
import csv
import os
from dotenv import load_dotenv
import time

def get_auth():
    if load_dotenv():
        account_id = os.getenv('ACCOUNT_ID').lower()
        account_pass = os.getenv('ACCOUNT_PASS')

        if account_id and account_pass:
            global basic
            basic = requests.auth.HTTPBasicAuth(account_id, account_pass)

        global print_request
        print_request = False
        if os.getenv('PRINT_REQUEST').lower() == "true":
            print_request = True

def get_datacite_api_response(url, endpoint, params=""):
    # Headers for all API requests
    headers = {
        "accept": "application/vnd.api+json",
    }

    request_url = "{}/{}".format(url, endpoint)
    if print_request:
        print("{}: {}".format(request_url, params))

    response = requests.request("GET", request_url, headers=headers, params=params, auth=basic)
    global api_request_count
    api_request_count += 1
    return response.json()

def get_total(response_json):
    return response_json["meta"]["total"]

def get_provider_count(response_json, provider_id):
    if "providers" in response_json["meta"]:
        for provider in response_json["meta"]["providers"]:
            if provider["id"] == provider_id:
                return provider["count"]
    return 0

def main():
    start = time.time()
    load_dotenv()
    get_auth()
    global api_request_count
    api_request_count = 0

    consortium_id = os.getenv('CONSORTIUM_ID').lower()
    year = os.getenv('YEAR')

    # Set base url (prod or test)
    url = "https://api.datacite.org"
    instance = "Production"
    if os.getenv('TEST_INSTANCE').lower() == "true":
        instance = "Test"
        url = "https://api.test.datacite.org"
        
    # Set monthly or quarterly breakdown; otherwise will only retrieve the year
    periods = {}
    period_keys_todate = []
    period_type = os.getenv('PERIOD').lower()
    if period_type == "monthly":
        for month in range (1, 13):
            periods[("{}-{:02d}".format(year, month))] = {"start_date": "{}-{:02d}-01".format(year, month),
                                                          "end_date": "{}-{:02d}-31".format(year, month)}
        del month
        period_keys_todate = list(periods.keys())[0:date.today().month]
    elif period_type == "quarterly":
        for quarter in range (1, 5):
            periods["Q{}".format(quarter)] = {"start_date": "{}-{:02d}-01".format(year, quarter*3 - 2),
                                              "end_date": "{}-{:02d}-31".format(year, quarter*3)}
        period_keys_todate = list(periods.keys())[0: ((date.today().month-1)//3) + 1]
        del quarter

    # Get list of consortium orgs
    consortium = get_datacite_api_response(url, "providers", {"consortium-id": consortium_id, "page[size]": 200})
    consortium_orgs_dict = {}
    for org in consortium["data"]:
        consortium_orgs_dict[org["id"]] = org
    consortium["data"] = consortium_orgs_dict
    del org, consortium_orgs_dict

    # Get consortium org details
    for org_id in consortium["data"]:
        # Set up stats
        consortium["data"][org_id]["stats"] = {}

        # Add empty period totals dict to consortium org
        consortium["data"][org_id]["stats"]["period_totals"] = {}
        for period in list(periods.keys()):
            consortium["data"][org_id]["stats"]["period_totals"][period] = 0
    del org_id

    # Get stats for the year by groups of 10 consortium organizations (max returned in facets)
    print("Getting {} DOIs for {}...".format(consortium_id.upper(), year))
    org_ids = list( consortium["data"].keys())
    batch_count = (len(org_ids) // 10) + 1
    batch_number = 0
    while batch_number < batch_count:
        batch = {}
        batch["org_ids"] = org_ids[(batch_number * 10):(batch_number * 10)+10]
        batch["provider_ids"] = ','.join(batch["org_ids"])
        print("Batch {} of {}: {}".format(batch_number+1, batch_count, batch["provider_ids"]))

        # get totals for up to 10 consortium orgs
        batch["cumulative"] = get_datacite_api_response(url, "dois", {"provider-id": batch["provider_ids"],
                                                                                     "page[size]": 0})
        batch["annual"] = get_datacite_api_response(url, "dois", {"provider-id": batch["provider_ids"],
                                                                     "registered": year,
                                                                     "page[size]": 0})

        # get periodic totals for up to 10 consortium orgs per batch
        batch["period"] = {}
        for period in period_keys_todate:
            batch["period"][period] = get_datacite_api_response(url, "dois", {"provider-id": batch["provider_ids"],
                                                                                      "registered": year,
                                                                                      "page[size]": 0,
                                                                                       "query": "registered:[{} TO {}]".format(periods[period]["start_date"], periods[period]["end_date"])
                                                                                       })
        del period

        for org_id in batch["org_ids"]:
            consortium["data"][org_id]["stats"]["cumulative_total"] = get_provider_count(batch["cumulative"], org_id)
            consortium["data"][org_id]["stats"]["annual_total"] = get_provider_count(batch["annual"], org_id)
            for period in period_keys_todate:
                consortium["data"][org_id]["stats"]["period_totals"][period] = get_provider_count(batch["period"][period], org_id)
        del period, org_id, batch
        batch_number +=1
    del batch_number, batch_count

    # Count DOIs from the consortium
    print("Counting {} DOIs by registration period...".format(consortium_id.upper()))
    consortium["stats"] = {}
    consortium["stats"]["annual_total"] = 0
    consortium["stats"]["cumulative_total"] = 0
    for period in list(periods.keys()):
        consortium["stats"][period] = 0
    del period
    for org_id in consortium["data"]:
        # Add the organization's period totals to the consortium's
        for period in list(periods.keys()):
            consortium["stats"][period] += consortium["data"][org_id]["stats"]["period_totals"][period]
        # Add the organization's annual total to the consortium's
        consortium["stats"]["annual_total"] += consortium["data"][org_id]["stats"]["annual_total"]
        # Add the organization's cumulative total to the consortium's
        consortium["stats"]["cumulative_total"] += consortium["data"][org_id]["stats"]["cumulative_total"]
    del org_id, period

    # Write DOI counts to csv file
    output_filename = "{}_{}_{}_dois_{}_{}.csv".format(date.today(), consortium_id.upper(), instance, year, period_type)
    with open(output_filename, mode='w') as csv_file:
        fieldnames = ["org_id", "org_name"] + list(periods.keys()) + ["annual_total", "cumulative_total"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for org_id in consortium["data"]:
            org_row = {"org_id": org_id, "org_name": consortium["data"][org_id]["attributes"]["name"]}
            org_row.update(consortium["data"][org_id]["stats"]["period_totals"])
            org_row["annual_total"] = consortium["data"][org_id]["stats"]["annual_total"]
            org_row["cumulative_total"] = consortium["data"][org_id]["stats"]["cumulative_total"]
            writer.writerow(org_row)
        del org_id, org_row
        consortium_row = {"org_id": consortium_id, "org_name": "All Consortium Organizations"}
        consortium_row.update(consortium["stats"])
        writer.writerow(consortium_row)

    end = time.time()
    duration = end - start
    print("Total time: {:.0f} minutes {:.2f} seconds".format(duration // 60, duration % 60))
    print("API request count: {}".format(api_request_count))

if __name__ == "__main__":
    main()