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

def get_datacite_api_response(url, endpoint, id, params=""):
    # Headers for all API requests
    headers = {
        "accept": "application/vnd.api+json",
    }

    request_url = "{}/{}".format(url, endpoint)
    if id:
        request_url = "{}/{}/{}".format(url, endpoint, id)
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
    former_org_ids = []

    # Set base url (prod or test)
    url = "https://api.datacite.org"
    instance = "Production"
    if os.getenv('TEST_INSTANCE').lower() == "true":
        instance = "Test"
        url = "https://api.test.datacite.org"
        
    # Set monthly or quarterly breakdown; otherwise will only retrieve the year
    period_keys = []
    period_keys_todate = []
    period_type = os.getenv('PERIOD').lower()
    if period_type == "monthly":
        for period in range (1, 13):
            period_keys.append("{}-{:02d}".format(year, period))
        period_keys_todate = period_keys[0:date.today().month]
    elif period_type == "quarterly":
        period_keys = ["Q1", "Q2", "Q3", "Q4"]
        period_keys_todate = ["Q1"]
        if date.today().month > 3:
            period_keys_todate.append("Q2")
        if date.today().month > 6:
            period_keys_todate.append("Q3")
        if date.today().month > 9:
            period_keys_todate.append("Q4")

    # Get list of consortium orgs
    consortium_data = get_datacite_api_response(url, "providers", "", {"consortium-id": consortium_id, "page[size]": 200})
    consortium_orgs_dict = {}
    for org in consortium_data["data"]:
        consortium_orgs_dict[org["id"]] = org
    consortium_data["data"] = consortium_orgs_dict

    # Get consortium org details
    for org_id in consortium_data["data"]:
        # Set up stats
        consortium_data["data"][org_id]["stats"] = {}

        # Add empty period totals dict to consortium org
        consortium_data["data"][org_id]["stats"]["period_totals"] = {}
        for period in period_keys:
            consortium_data["data"][org_id]["stats"]["period_totals"][period] = 0

    # Get stats for the year by groups of 10 consortium organizations (max returned in facets)
    print("Getting {} DOIs for {}...".format(consortium_id.upper(), year))
    org_ids = list( consortium_data["data"].keys())
    batch_count = (len(org_ids) // 10) + 1
    batch_number = 0
    while batch_number < batch_count:
        batch_org_ids = org_ids[(batch_number * 10):(batch_number * 10)+10]
        batch_provider_ids = ','.join(batch_org_ids)
        print("Batch {} of {}: {}".format(batch_number+1, batch_count, batch_provider_ids))

        # get cumulative totals for up to 10 consortium orgs
        batch_response = get_datacite_api_response(url, "dois", "", {"provider-id": batch_provider_ids,
                                                                                     "page[size]": 0})
        for org_id in batch_org_ids:
            consortium_data["data"][org_id]["stats"]["cumulative_total"] = get_provider_count(batch_response, org_id)

        # get annual totals for up to 10 consortium orgs
        batch_response = get_datacite_api_response(url, "dois", "", {"provider-id": batch_provider_ids,
                                                                                  "registered": year,
                                                                                  "page[size]": 0})
        for org_id in batch_org_ids:
            consortium_data["data"][org_id]["stats"]["annual_total"] = get_provider_count(batch_response, org_id)

        # get periodic totals for up to 10 consortium orgs per batch
        for period in period_keys_todate:
            if period_type == "monthly":
                start_date = "{}-01".format(period)
                end_date = "{}-31".format(period)
            elif period_type == "quarterly":
                if period == "Q1":
                    start_date = "{}{}".format(year, "-01-01")
                    end_date = "{}{}".format(year, "-03-31")
                elif period == "Q2":
                    start_date = "{}{}".format(year, "-04-01")
                    end_date = "{}{}".format(year, "-06-30")
                elif period == "Q3":
                    start_date = "{}{}".format(year, "-07-01")
                    end_date = "{}{}".format(year, "-09-30")
                elif period == "Q4":
                    start_date = "{}{}".format(year, "-10-01")
                    end_date = "{}{}".format(year, "-12-31")

            batch_response = get_datacite_api_response(url, "dois", "", {"provider-id": batch_provider_ids,
                                                                                      "registered": year,
                                                                                      "page[size]": 0,
                                                                                       "query": "registered:[{} TO {}]".format(start_date, end_date)
                                                                                       })
            for org_id in batch_org_ids:
                consortium_data["data"][org_id]["stats"]["period_totals"][period] = get_provider_count(batch_response, org_id)

        batch_number +=1

    # Count DOIs from the consortium
    print("Counting {} DOIs by registration period...".format(consortium_id.upper()))
    consortium_data["stats"] = {}
    consortium_data["stats"]["annual_total"] = 0
    consortium_data["stats"]["cumulative_total"] = 0
    for period in period_keys:
        consortium_data["stats"][period] = 0
    for org_id in consortium_data["data"]:
        # Add the organization's period totals to the consortium's
        for period in period_keys:
            consortium_data["stats"][period] += consortium_data["data"][org_id]["stats"]["period_totals"][period]
        # Add the organization's annual total to the consortium's
        consortium_data["stats"]["annual_total"] += consortium_data["data"][org_id]["stats"]["annual_total"]
        # Add the organization's cumulative total to the consortium's
        consortium_data["stats"]["cumulative_total"] += consortium_data["data"][org_id]["stats"]["cumulative_total"]

    # Write DOI counts to csv file
    output_filename = "{}_{}_{}_dois_{}_{}.csv".format(date.today(), consortium_id.upper(), instance, year, period_type)
    with open(output_filename, mode='w') as csv_file:
        fieldnames = ["org_id", "org_name"] + period_keys + ["annual_total", "cumulative_total"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for org_id in consortium_data["data"]:
            org_row = {"org_id": org_id, "org_name": consortium_data["data"][org_id]["attributes"]["name"]}
            org_row.update(consortium_data["data"][org_id]["stats"]["period_totals"])
            org_row["annual_total"] = consortium_data["data"][org_id]["stats"]["annual_total"]
            org_row["cumulative_total"] = consortium_data["data"][org_id]["stats"]["cumulative_total"]
            writer.writerow(org_row)
        consortium_row = {"org_id": consortium_id, "org_name": "All Consortium Organizations"}
        consortium_row.update(consortium_data["stats"])
        writer.writerow(consortium_row)

    end = time.time()
    duration = end - start
    print("Total time: {:.0f} minutes {:.2f} seconds".format(duration // 60, duration % 60))
    print("API request count: {}".format(api_request_count))

if __name__ == "__main__":
    main()