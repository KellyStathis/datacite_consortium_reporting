This project exports the number of DOIs registered by a DataCite consortium's consortium organizations per month, for a given year.

## Configuration

Create an .env file with:
- credentials for authentication (`ACCOUNT_ID` and `ACCOUNT_PASS`)
- the `CONSORTIUM_ID` for the report to retrieve (can be the same as or different from `ACCOUNT_ID`)  
- set `TEST_INSTANCE=true` to run using the test instance (api.test.datacite.org); otherwise, default is the production instance (api.datacite.org).
- set `YEAR` to the year from which to pull DOI registration statistics
- set `PRINT_REQUEST=true` top print each API request (for debugging)
- set `PERIOD` to `monthly` or `quarterly` to retrieve statistics by month or quarter within the specified year; otherwise, default is yearly

Example .env:

```
ACCOUNT_ID=abcd
ACCOUNT_PASS=password
CONSORTIUM_ID=abcd
TEST_INSTANCE=false
YEAR=2024
PRINT_REQUEST=false
PERIOD=quarterly
```

## Usage

`pipenv install`  
`pipenv run python consortium_reporting.py`

