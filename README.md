This project exports the number of DOIs registered by a DataCite consortium's consortium organizations per month, for a given year.

## Configuration

Create an .env file with the consortium's credentials (`CONSORTIUM_ID` and `CONSORTIUM_PASS`). 

Set `TEST_INSTANCE=true` to run using test (api.test.datacite.org). Otherwise, the script will default to the production API (api.datacite.org).

Set `YEAR` to the year from which to pull DOI registration statistics.

Set `FORMER_MEMBERS` to a semicolon-delimited list of consortium organizations to exclude from reporting.

Example .env:

```
CONSORTIUM_ID=consortium_example_id
CONSORTIUM_PASS=consortium_example_pass
TEST_INSTANCE=false
YEAR=2021	
FORMER_MEMBERS=consortiumorg1;consortiumorg2
```

## Usage

`pipenv install`  
`pipenv run python consortium_reporting.py`

